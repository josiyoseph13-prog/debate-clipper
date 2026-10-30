# Model and asset licence table

One verification-only ASR model is now stored locally. Its MIT licence, pinned
model card, upstream revision and every file hash are recorded in
`assets/models/registry.json` and `reports/supplied_media/registered_asr.json`.
Having working inference/recovery does not prove word/name accuracy or select
the production model. Other learned stacks remain uninstalled and gated.

| Asset | Version/hash | Licence | Use | Status |
|---|---|---|---|---|
| Systran/faster-whisper-base | revision `ebe41f70d5b6dfa9166e2c581c45c9c0cfc57b66`; model145,217,532 bytes; SHA256 `d01c3014881c9c6f3133c182f3d2887eb6ca1c789a7538c5c007196857a0a6a9` | MIT; `assets/models/whisper_base/LICENSE`, pinned `MODEL_CARD.md` | offline CPU int8 ASR verification | copied from existing user-local cache after matching upstream LFS/blob hashes; `default_enabled:false`, `accuracy_verified:false` |
| sherpa-onnx diarization weights | user-selected | verify each model card | optional offline diarization | disabled until installed |
| MediaPipe Tasks models | user-selected | verify upstream terms | optional face/landmark/reaction signals | disabled until installed |
| Inter fonts in `assets/fonts` | workspace supplied | verify source licence | compatibility fallback | placeholder/compatibility |
| Montserrat ExtraBold | `d3ac6a843d3ba6d5cafd44cf39e437055c8aed7e261010f595f57d3c7b3e2c1b` | `assets/fonts/Montserrat-OFL.txt` (SIL OFL) | current measured caption fallback | upstream JulietaUla/Montserrat; six-word shape comparison, not exact CapCut font identification |
| Montserrat Black | `ea67b37f8776eebea135cd1fe9adeaf6f9427683e8dc11ab8398b6be5f102c60` | same SIL OFL | reference font comparison | preserved comparison asset |
| Bebas Neue Regular | `08e4623805102d819f58601e46e345648846075e363b2ceb23313c2d1c83ec73` | `assets/fonts/BebasNeue-OFL.txt` (SIL OFL) | reference font comparison | Google Fonts; not selected for default captions |
| Poppins ExtraBold | `f2ab17c1a63a0ecc12c2461848fc8a469395e3cd2d641803e889c643d9f958e1` | `assets/fonts/Poppins-OFL.txt` (SIL OFL) | historical caption profile | downloaded unmodified from Google Fonts, 2026-10-05 |
| Poppins SemiBold | `d3bf1bdaf0550e83da9ac0b1d1d9fe6db086835a83aa28578e609a394b9a0286` | `assets/fonts/Poppins-OFL.txt` (SIL OFL) | headline | downloaded unmodified from Google Fonts, 2026-10-05 |
| Poppins Regular | `7e65201e9b79159e2300267cc885e16c8dcef2424cdfa09a29bfb0980a94a7ba` | `assets/fonts/Poppins-OFL.txt` (SIL OFL) | handle | downloaded unmodified from Google Fonts, 2026-10-05 |
| Anton Regular | `a4ba3a92350ebb031da0cb47630ac49eb265082ca1bc0450442f4a83ab947cab` | `assets/fonts/Anton-OFL.txt` (SIL OFL) | live wordmark fallback | downloaded unmodified from Google Fonts, 2026-10-05 |
| Noto Color Emoji | `4fb036f372153c0eb66122b76783bd4aa8c3972f0cb9bd9d0a58bd8a16521540` | `assets/fonts/NotoColorEmoji-OFL.txt` (SIL OFL) | optional emoji | downloaded unmodified from Debian `fonts-noto-color-emoji_2.051-1_all.deb`; real Pillow raster verified on Linux |
| Supplied Political Lens emblem | JPG200×200; `af370b2cfc5aa7ab80723d7035ebf4f151c730acd6ca3fe47e0dc933a36ed30c` | user-supplied genuine branding; no separate redistribution grant inferred | direct artwork resize/mask | `reports/supplied_media/logo_render.json`; not a placeholder; separate wordmark absent |
| Linux FFmpeg verification build | BtbN `n8.1.3-14-g330caae0c1-20261005`; archive SHA256 `8c0aeb9a4d4bc9e269aff5280f3f67fcdca58116158926b9d3f39f6efb5c7569` | GPL build; upstream obligations apply to redistribution | render/probe | actual libass/HarfBuzz/libx264; historical different archive retained in DECISIONS.md |
| Native Windows FFmpeg verification build | Gyan9.0.2 essentials; archive SHA256 `4705843ccaaf54257c16ad90f3e952ece33c17df964ecf7bfdbb0f49c7171077` | GPL build; upstream obligations apply to redistribution | native render/probe | publisher checksum matches; actual required capabilities and executable hashes in `reports/native_windows/summary.json` |

Do not distribute downloaded weights or a full FFmpeg binary without reviewing their licences and obligations.

Font sources: `https://github.com/google/fonts/tree/main/ofl/poppins`, `https://github.com/google/fonts/tree/main/ofl/anton`. These are font assets, not learned model weights.
Montserrat source: `https://github.com/JulietaUla/Montserrat`.
Bebas Neue source: `https://github.com/google/fonts/tree/main/ofl/bebasneue`.

Noto source: `https://deb.debian.org/debian/pool/main/f/fonts-noto-color-emoji/fonts-noto-color-emoji_2.051-1_all.deb`.
FFmpeg verification archive: `https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-n8.1-latest-linux64-gpl-shared-8.1.tar.xz`.
The `latest` URL is mutable; verify the recorded SHA-256 when reproducing this run.

Windows FFmpeg archive: `https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.7z`.
Pinned Whisper card: `https://huggingface.co/Systran/faster-whisper-base/raw/ebe41f70d5b6dfa9166e2c581c45c9c0cfc57b66/README.md`.
Native optional-ASR package profile: `requirements-asr-windows.lock` (51 pins).
`reports/native_windows/asr_wheel_hashes.txt` records an ignore-installed,
binary-only, hash-required resolution of all wheels. This is distinct from the
earlier unpinned optional install. Core profile stays `requirements.lock`.

FCPXML acceptance uses the already installed system `libxml2.so.16`, version
2.15.2 (MIT upstream), through its actual DTD validator. Apple's complete1.10DTD
is explicitly retrieved to `work/job_fcpxml_acceptance/`; its copyright notice
is retained and it is not bundled as a permissively licensed product asset.
Schema/source hashes and actual validation are in `reports/current_checks/fcpxml.json`.
