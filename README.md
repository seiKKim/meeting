# 음성 녹음 → 회의록 (로컬)

녹음 파일을 **faster-whisper**로 받아쓰고, **로컬 Ollama**로 회의록을 정리해
**Obsidian Vault**에 마크다운으로 저장합니다. 전부 로컬에서 동작합니다(외부 전송 없음).

## 파이프라인
```
오디오(m4a/mp3/wav) → faster-whisper(STT, GPU) → Ollama(gemma3 요약) → Obsidian .md
```

## 사용법

### 1) 가장 쉬운 방법 — 입력함(inbox)에 넣고 더블클릭  ⭐
녹음 파일을 **`회의록` 폴더**(`C:\SeikProject\meeting\회의록`)에 넣고
`회의록만들기.bat`을 **더블클릭**하면, 폴더 안의 모든 녹음을 한 번에 회의록으로 변환합니다.
처리된 원본은 `회의록\처리완료\`로 자동 이동되어 중복 처리되지 않습니다.

### 2) 드래그&드롭
특정 파일만 처리하려면 그 파일을 `회의록만들기.bat` 위에 끌어다 놓으세요.

### 3) 명령어
```powershell
# 입력함 전체 일괄 처리
.\.venv\Scripts\python.exe meeting.py

# 특정 파일만
.\.venv\Scripts\python.exe meeting.py "회의록\주간회의.m4a" --title "주간 정기회의"
```

주요 옵션:
| 옵션 | 설명 | 기본값 |
|------|------|--------|
| `--title` | 회의 제목(파일명/노트명에 사용) | 파일명 |
| `--model` | Whisper 모델 `small`/`medium`/`large-v3` | `medium` |
| `--device` | `auto`/`cuda`/`cpu` | `auto` |
| `--ollama-model` | 요약 모델 | `gemma3:latest` |

## 설정 — `config.json`
- `vault_meeting_dir` : 회의록 저장 폴더 (현재 `C:\저장소\옵시디언\회의록`)
- `whisper_model` : 기본 Whisper 모델. **정확도 더 원하면 `large-v3`**(첫 실행 시 ~3GB 다운로드, GPU 4GB에서 동작)
- `ollama_model` : 요약 모델. 기본 **`gemma4:12b`**(디테일 최상, 단 4GB GPU엔 안 올라가 CPU 실행 → 회의 1건당 ~17분). 빠르게 쓰려면 `gemma3:latest`(~3분).
- `ollama_num_ctx` : 컨텍스트 길이. 기본 **24576**. 실제 회의 녹취록이 ~15,000토큰이라 8192면 잘림. 매우 긴 회의는 더 키우세요(gemma4는 256K까지 지원).

### 모델별 비교(실측, 4GB GPU + 32GB RAM, 동일 실제 녹음)
| 모델 | 1건 소요 | 특징 |
|------|---------|------|
| `gemma4:12b` | ~17분(CPU) | 디테일·고유명사·수치 촘촘 (그라파이/5초목표/5천건 등) |
| `gemma3:latest` | ~3분 | 빠르고 참석자 실명·맥락 잘 잡음 |

> 중요한 회의만 12b로: `... meeting.py "파일" --ollama-model gemma4:12b`
> 빠르게: `... --ollama-model gemma3:latest`

## 결과물
- 회의록: `회의록/YYYY-MM-DD_HHMM_제목.md`
  (한 줄 요약 / 핵심 / 논의 / 결정 / 액션아이템 / 후속 + 접힌 전체 녹취록)
- 원본 녹취록: `transcripts/…​.txt`

## 환경 메모
- GPU(CUDA) 가속을 위해 `nvidia-cublas-cu12`, `nvidia-cudnn-cu12`(pip 휠)를 설치했고,
  `meeting.py`가 시작 시 해당 DLL 경로를 자동 등록합니다.
  GPU 사용이 안 되면 자동으로 CPU로 폴백합니다(느리지만 동작).
- Ollama가 실행 중이어야 합니다(`ollama serve` 또는 트레이 앱).

## 처음 받는 사람용 설치
```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install faster-whisper nvidia-cublas-cu12 "nvidia-cudnn-cu12==9.*"
```
