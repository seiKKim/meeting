# -*- coding: utf-8 -*-
"""
음성 녹음 -> (faster-whisper STT) -> (로컬 Ollama 요약) -> Obsidian 회의록(.md)

사용법:
    python meeting.py <오디오파일> [--title "회의 제목"]
                      [--model medium] [--device auto]
                      [--ollama-model qwen2.5:3b] [--keep-transcript]

예시:
    python meeting.py audio/20260606_주간회의.m4a --title "주간 정기회의"
"""
import argparse
import datetime as dt
import json
import os
import re
import sys
import urllib.request
import urllib.error

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")


def _register_cuda_dlls():
    """pip로 설치한 nvidia CUDA 휠(cublas/cudnn)의 DLL 경로를 PATH에 등록.
    시스템에 CUDA 툴킷이 없어도 GPU 추론이 가능하게 한다."""
    if not hasattr(os, "add_dll_directory"):
        return
    try:
        import importlib.util
    except Exception:  # noqa: BLE001
        return
    for pkg in ("nvidia.cublas", "nvidia.cudnn"):
        try:
            spec = importlib.util.find_spec(pkg)
            if spec and spec.submodule_search_locations:
                bin_dir = os.path.join(list(spec.submodule_search_locations)[0], "bin")
                if os.path.isdir(bin_dir):
                    os.add_dll_directory(bin_dir)
                    # ctranslate2는 CUDA DLL을 명시적 LoadLibrary로 지연 로딩하므로
                    # add_dll_directory만으로는 부족 -> PATH에도 직접 추가
                    if bin_dir not in os.environ.get("PATH", ""):
                        os.environ["PATH"] = bin_dir + os.pathsep + os.environ.get("PATH", "")
        except Exception:  # noqa: BLE001
            pass


_register_cuda_dlls()


def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def log(msg):
    print(f"[meeting] {msg}", flush=True)


# ---------------------------------------------------------------------------
# 1) STT : faster-whisper
# ---------------------------------------------------------------------------
def transcribe(audio_path, cfg, model_override=None, device_override=None):
    from faster_whisper import WhisperModel

    model_name = model_override or cfg["whisper_model"]
    device = device_override or cfg["whisper_device"]
    language = cfg["whisper_language"]

    def run(dev):
        compute = "int8_float16" if dev == "cuda" else "int8"
        log(f"Whisper 모델 로딩: model={model_name}, device={dev}, compute={compute}")
        model = WhisperModel(model_name, device=dev, compute_type=compute)
        segments, info = model.transcribe(
            audio_path,
            language=language,
            vad_filter=True,
            beam_size=5,
        )
        log(f"음성 인식 시작 (감지 언어={info.language}, 확률 {info.language_probability:.2f})...")
        parts = []
        for seg in segments:  # 추론 오류는 여기서 발생 -> try 안에서 모두 소비
            ts = str(dt.timedelta(seconds=int(seg.start)))
            text = seg.text.strip()
            if text:
                parts.append((ts, text))
                print(f"  [{ts}] {text}", flush=True)
        return parts

    # device=auto 이면 cuda 시도 후 (로딩/추론) 실패 시 cpu 폴백
    candidates = ("cuda", "cpu") if device == "auto" else (device,)
    parts = None
    for dev in candidates:
        try:
            parts = run(dev)
            break
        except Exception as e:  # noqa: BLE001
            log(f"{dev} 처리 실패 ({type(e).__name__}: {e})")
            if dev != candidates[-1]:
                log("-> CPU로 재시도합니다.")
    if parts is None:
        raise RuntimeError("음성 인식에 실패했습니다.")

    full_text = "\n".join(t for _, t in parts)
    timestamped = "\n".join(f"[{ts}] {t}" for ts, t in parts)
    return full_text, timestamped


# ---------------------------------------------------------------------------
# 2) 요약 : 로컬 Ollama
# ---------------------------------------------------------------------------
PROMPT_TEMPLATE = """당신은 전문 회의록 작성자입니다. 아래는 음성 인식(STT)으로 변환된 회의 녹취록입니다.
STT 특성상 오탈자·띄어쓰기 오류가 있을 수 있으니 문맥으로 자연스럽게 보정해서 이해하세요.

다음 형식의 한국어 마크다운 회의록을 작성하세요. 녹취록에 없는 내용은 절대 지어내지 마세요.

## 한 줄 요약
- (회의 전체를 한 문장으로)

## 핵심 요약
- (3~6개 불릿)

## 주요 논의 내용
### (주제 1)
- 내용
### (주제 2)
- 내용

## 결정 사항
- (합의/결정된 것. 없으면 "없음")

## 액션 아이템
- [ ] (할 일) — 담당: (추정 가능하면) / 기한: (언급되면)

## 후속 논의 필요
- (미해결 사항. 없으면 "없음")

---
[녹취록 시작]
{transcript}
[녹취록 끝]
"""


def _read_file(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except OSError:
        return None


def load_prompt_template(cfg):
    """prompt.md 가 있으면 그 내용을, 없으면 내장 PROMPT_TEMPLATE 를 사용."""
    path = cfg.get("prompt_file") or os.path.join(BASE_DIR, "prompt.md")
    if not os.path.isabs(path):
        path = os.path.join(BASE_DIR, path)
    text = _read_file(path)
    if text and "{transcript}" in text:
        log(f"프롬프트 사용: {path}")
        return text
    log("prompt.md 없음 -> 내장 기본 프롬프트 사용")
    return PROMPT_TEMPLATE


def load_glossary(cfg):
    """glossary.md(오인식 보정 사전) 내용. 없으면 빈 안내."""
    path = cfg.get("glossary_file") or os.path.join(BASE_DIR, "glossary.md")
    if not os.path.isabs(path):
        path = os.path.join(BASE_DIR, path)
    text = _read_file(path)
    return text.strip() if text else "(등록된 보정 항목 없음)"


def summarize_with_ollama(transcript, cfg, model_override=None):
    model = model_override or cfg["ollama_model"]
    url = cfg["ollama_url"].rstrip("/") + "/api/generate"
    template = load_prompt_template(cfg)
    glossary = load_glossary(cfg)
    # transcript/glossary 안에 중괄호가 있어도 안전하도록 .format 대신 replace 사용
    prompt = template.replace("{glossary}", glossary).replace("{transcript}", transcript)

    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "num_ctx": cfg.get("ollama_num_ctx", 8192),
            "temperature": 0.3,
        },
    }
    log(f"Ollama 요약 요청: model={model}")
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}
    )
    timeout = cfg.get("ollama_timeout", 3600)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as e:
        raise RuntimeError(
            f"Ollama 호출 실패: {e}. Ollama가 실행 중인지(ollama serve) 확인하세요."
        )
    return body.get("response", "").strip()


# ---------------------------------------------------------------------------
# 3) Obsidian 저장
# ---------------------------------------------------------------------------
def slugify(name):
    name = re.sub(r"[\\/:*?\"<>|]", "", name)
    return name.strip().replace(" ", "_")[:60]


def save_to_obsidian(cfg, title, notes_md, timestamped, audio_path, now):
    vault_dir = cfg["vault_meeting_dir"]
    os.makedirs(vault_dir, exist_ok=True)

    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M")
    fname = f"{now.strftime('%Y-%m-%d_%H%M')}_{slugify(title)}.md"
    fpath = os.path.join(vault_dir, fname)

    frontmatter = (
        "---\n"
        f"title: {title}\n"
        f"date: {date_str} {time_str}\n"
        "type: 회의록\n"
        "tags: [회의록]\n"
        f"source: {os.path.basename(audio_path)}\n"
        "---\n\n"
    )
    # 모델 출력(notes_md)이 자체적으로 제목 헤딩을 생성하므로 중복 헤더는 최소화
    header = f"> 처리: {date_str} {time_str} · 원본: {os.path.basename(audio_path)}\n\n"

    transcript_block = (
        "\n\n---\n\n"
        "> [!note]- 전체 녹취록 (펼치기)\n"
        + "\n".join("> " + line for line in timestamped.splitlines())
        + "\n"
    )

    with open(fpath, "w", encoding="utf-8") as f:
        f.write(frontmatter + header + notes_md + transcript_block)

    return fpath


# ---------------------------------------------------------------------------
def process_one(audio_path, cfg, args, title=None):
    """오디오 1개 -> 회의록 .md. 저장 경로 반환."""
    title = title or os.path.splitext(os.path.basename(audio_path))[0]
    now = dt.datetime.now()

    full_text, timestamped = transcribe(audio_path, cfg, args.model, args.device)
    if not full_text.strip():
        log("인식된 텍스트가 없습니다. 건너뜁니다.")
        return None

    if args.keep_transcript or cfg.get("save_raw_transcript"):
        tdir = cfg.get("transcript_dir", BASE_DIR)
        os.makedirs(tdir, exist_ok=True)
        tpath = os.path.join(tdir, f"{now.strftime('%Y-%m-%d_%H%M')}_{slugify(title)}.txt")
        with open(tpath, "w", encoding="utf-8") as f:
            f.write(timestamped)
        log(f"녹취록 저장: {tpath}")

    # 타임스탬프가 포함된 전사를 넘겨야 '(MM:SS ~ MM:SS)' 구간 요약이 가능
    notes_md = summarize_with_ollama(timestamped, cfg, args.ollama_model)
    if not notes_md:
        log("Ollama 응답이 비어 있습니다. 건너뜁니다.")
        return None

    return save_to_obsidian(cfg, title, notes_md, timestamped, audio_path, now)


def process_inbox(cfg, args):
    """입력함(inbox) 폴더의 모든 오디오를 처리하고 처리완료 폴더로 이동."""
    inbox = cfg.get("inbox_dir")
    if not inbox or not os.path.isdir(inbox):
        log(f"입력 폴더가 없습니다: {inbox}")
        sys.exit(1)
    exts = tuple(e.lower() for e in cfg.get("audio_exts", [".m4a", ".mp3", ".wav"]))
    done_dir = os.path.join(inbox, cfg.get("processed_subdir", "처리완료"))

    files = [
        os.path.join(inbox, n)
        for n in sorted(os.listdir(inbox))
        if os.path.isfile(os.path.join(inbox, n)) and n.lower().endswith(exts)
    ]
    if not files:
        log(f"입력 폴더에 처리할 오디오가 없습니다: {inbox}")
        log("녹음 파일을 이 폴더에 넣고 다시 실행하세요.")
        return

    log(f"입력함 처리 시작: {len(files)}개 파일")
    ok = 0
    for i, audio_path in enumerate(files, 1):
        log(f"=== [{i}/{len(files)}] {os.path.basename(audio_path)} ===")
        try:
            fpath = process_one(audio_path, cfg, args)
            if fpath:
                log(f"회의록 저장 완료 -> {fpath}")
                os.makedirs(done_dir, exist_ok=True)
                dest = os.path.join(done_dir, os.path.basename(audio_path))
                if os.path.exists(dest):  # 이름 충돌 방지
                    base, ext = os.path.splitext(os.path.basename(audio_path))
                    dest = os.path.join(done_dir, f"{base}_{dt.datetime.now().strftime('%H%M%S')}{ext}")
                os.replace(audio_path, dest)
                log(f"원본 이동 -> {dest}")
                ok += 1
        except Exception as e:  # noqa: BLE001
            log(f"처리 실패({os.path.basename(audio_path)}): {type(e).__name__}: {e}")
    log(f"완료: {ok}/{len(files)}개 성공")


def main():
    cfg = load_config()
    p = argparse.ArgumentParser(description="음성 녹음 -> Ollama 회의록 -> Obsidian")
    p.add_argument("audio", nargs="?", default=None,
                   help="오디오 파일 경로. 생략하면 입력함(회의록 폴더) 전체를 일괄 처리")
    p.add_argument("--title", default=None, help="회의 제목 (기본: 파일명)")
    p.add_argument("--model", default=None, help="Whisper 모델 (tiny/base/small/medium/large-v3)")
    p.add_argument("--device", default=None, help="auto/cuda/cpu")
    p.add_argument("--ollama-model", default=None, help="Ollama 모델명")
    p.add_argument("--keep-transcript", action="store_true", help="녹취록 txt 별도 저장")
    args = p.parse_args()

    # 인자가 없으면 입력함(회의록 폴더) 일괄 처리 모드
    if not args.audio:
        process_inbox(cfg, args)
        return

    audio_path = os.path.abspath(args.audio)
    if not os.path.exists(audio_path):
        log(f"오디오 파일을 찾을 수 없습니다: {audio_path}")
        sys.exit(1)

    fpath = process_one(audio_path, cfg, args, title=args.title)
    if fpath:
        log(f"회의록 저장 완료 -> {fpath}")
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
