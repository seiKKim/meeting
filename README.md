# 🎙️ 회의록 자동화 시스템

> 녹음 파일을 폴더에 넣고 더블클릭 한 번으로 회의록 완성

음성 녹음을 **AI가 자동으로 받아쓰고 요약**해 Obsidian에 마크다운 파일로 저장합니다.
모든 처리가 **내 PC에서만** 이루어져 외부로 데이터가 전송되지 않습니다.

```
🎙️ 녹음 파일  →  📝 AI 받아쓰기(Whisper)  →  🤖 AI 요약(Ollama)  →  📓 Obsidian 저장
```

## 주요 기능

- **더블클릭 실행** — `회의록만들기.bat`을 더블클릭하면 폴더 안의 모든 녹음을 한 번에 처리
- **한국어 최적화** — 오인식 보정 사전(`glossary.md`)으로 회사 도메인 용어 자동 교정
- **타임스탬프 회의록** — `(11:25 ~ 13:18)` 형태의 구간별 요약으로 원본 녹음과 대조 가능
- **100% 로컬** — 인터넷 없이 동작, 녹음 내용이 외부로 나가지 않음
- **Obsidian 연동** — 핵심요약 / 액션아이템 / 결정사항 / 전체 녹취록을 마크다운으로 자동 저장

## 사용법

1. 녹음 파일(`.m4a` `.mp3` `.wav` 등)을 `회의록/` 폴더에 복사
2. `회의록만들기.bat` 더블클릭
3. Obsidian에서 완성된 회의록 확인

처리된 녹음은 `회의록/처리완료/`로 자동 이동되어 중복 처리되지 않습니다.

## 생성되는 회의록 구조

| 섹션 | 내용 |
|------|------|
| 📌 핵심 요약 | 회의 전체를 6~10개 핵심으로 압축 |
| 🔑 주요 키워드 | 등장한 핵심 용어 |
| ✅ 액션 아이템 | 담당자·기한 포함 TODO 목록 |
| 🎯 결정 사항 | 합의·확정된 내용 |
| 👥 발화자 분석 | 참석자별 역할·발언 분석 |
| 💬 주요 대화 | 타임스탬프 구간별 요약 |
| ❓ 후속 논의 | 미해결·추가 검토 사항 |

## 설치

```powershell
# 패키지 설치 (최초 1회)
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install faster-whisper nvidia-cublas-cu12 "nvidia-cudnn-cu12==9.*"

# Ollama 모델 설치 (최초 1회, ~8GB)
ollama pull gemma4:12b
```

## 설정 (`config.json`)

| 항목 | 설명 |
|------|------|
| `vault_meeting_dir` | Obsidian 회의록 저장 경로 |
| `ollama_model` | 요약 모델. `gemma4:12b`(고품질, ~17분) / `gemma3:latest`(빠름, ~3분) |
| `whisper_model` | STT 모델. `small` / `medium`(기본) / `large-v3`(최고 정확도) |

커스터마이징은 `prompt.md`(회의록 양식)와 `glossary.md`(오인식 사전)를 메모장으로 편집하면 됩니다.

## 설치 가이드

👉 **[설치부터 사용까지 상세 가이드](https://meeting-three-omega.vercel.app)**

## 기술 스택

- **STT** — [faster-whisper](https://github.com/SYSTRAN/faster-whisper) (GPU 가속)
- **LLM** — [Ollama](https://ollama.com) + gemma4:12b
- **출력** — [Obsidian](https://obsidian.md) Markdown Vault
