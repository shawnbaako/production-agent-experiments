# Tesla P40 at a 125 W limit: clock, power and temperature over ten weeks

These numbers come from one P40 that served a dense 27B model around the clock. Nothing was run
for this note. The data is a 30 s `nvidia-smi` sampler (about 190k rows, 2026-09-03 to
2026-11-15) joined with llama-server's own `print_timing` lines.

## What we found

- **At the power limit, heat costs clock speed well before the card throttles.** With power pinned
  at about 120 W, the SM clock under load holds about 1230 MHz up to 65 °C. It then falls to
  1139 MHz at 70–74 °C and 1075 MHz at 80–84 °C, about 13% down. That is far below the card's
  92 °C slowdown. The likely cause is that hotter silicon leaks more, so the same power budget
  buys a lower clock.
- **The idle downclock matters most.** Forced to P8 when idle, the card sits at 31 °C and 11 W.
  Left at P0 with the model loaded, it idles at 60 °C and 55 W. Each burst of work then starts
  that much closer to the range where it loses clock.
- **Below 65 °C, speed does not depend on temperature:** about 186 tok/s prefill on a 12k-token
  prompt and about 16 tok/s decode with an MTP draft.
- **Speed above 65 °C is unmeasured.** None of the requests with timings ran hotter than 69 °C.
  The clock loss above that is measured, but we have not measured the matching loss in tokens per
  second.

## Setup

- Tesla P40 24 GB, passive heatsink, in an open desktop case with extra case fans and no server
  airflow. i7-6700K host, PCIe 3.0 x16.
- Power limit **125 W** (`nvidia-smi -pl 125`, the card's minimum; the default is 250 W). Driver
  580.178.04.
- llama.cpp upstream commit `34af94cd9` (2026-08-17), CUDA 12.9, `sm_61`,
  `GGML_CUDA_FORCE_MMQ=ON`, CUDA graphs on.
- Model: Qwen3.8-27B IQ4_XS, `-ngl 999 -fa on -c 131072 -ctk q8_0 -ctv q8_0 -np 1`, MTP draft
  (`--spec-type draft-mtp --spec-draft-n-max 4 --spec-draft-p-min 0.75`), median draft
  acceptance 0.83.

## SM clock under load by temperature

The table covers every sample at 90% utilisation or more.

| Temp °C | Samples | Median SM MHz | SM capped at 544 MHz | Median power W |
|---|---:|---:|---:|---:|
| 40-44 | 266 | 1227 | 0% | 124.8 |
| 50-54 | 432 | 1240 | 0% | 122.5 |
| 60-64 | 282 | 1227 | 0% | 122.0 |
| 65-69 | 348 | 1202 | 0% | 121.1 |
| 70-74 | 348 | 1139 | 0% | 119.9 |
| 75-79 | 603 | 1126 | 0.7% | 119.5 |
| 80-84 | 777 | 1050 | 28% | 116.8 |
| 85-89 | 1145 | 544 | 92% | 91.2 |

Above 84 °C our watchdog caps the clock (see below), so the last two rows mostly show that cap.
Leaving the capped samples out, the median is 1075 MHz at 80–84 °C. At 125 W the card never comes
near its 1531 MHz maximum boost.

## Idle by performance state

The table covers every sample at 0% utilisation.

| Idle state | Samples | Median °C | p90 °C | Median W |
|---|---:|---:|---:|---:|
| P8 via nvidia-pstated | 167,906 | 31 | 40 | 11.0 |
| P0, model loaded | 16,102 | 60 | 74 | 55.5 |

We run `nvidia-pstated` only while the card is idle. A file watch on the llama-server log stops it
on the next request. Left to its own load detection, pstated kept the card at P8 under 100%
utilisation.

## Speed by temperature

These are the 82 logged requests, from one 38-hour window. Most were a recurring prompt of about
12k tokens.

| Phase | Temp °C | n | Median tok/s | Median tokens | SM MHz |
|---|---|---:|---:|---:|---:|
| prefill | 45-49 | 34 | 186.1 | 12,073 | 1215 |
| prefill | 50-54 | 42 | 185.8 | 12,072 | 1202 |
| prefill | 60-64 | 3 | 181.9 | 12,074 | 1177 |
| decode | 50-54 | 34 | 16.2 | 245 | 1265 |
| decode | 55-59 | 22 | 16.2 | 243 | 1258 |
| decode | 60-64 | 3 | 15.9 | 185 | 1227 |

## What kept the card running

A systemd timer checks temperature every 20 s:

- **80 °C:** it logs a warning.
- **84 °C:** it runs `nvidia-smi -ac 3615,544`, which keeps memory at full clock and caps the SM
  clock at 544 MHz. Power drops to 82–92 W, but under sustained load the card still heats up.
- **88 °C:** it stops the server. The server restarts at 72 °C, and the cap is lifted at 74 °C.
  The median stop-to-restart gap was 140 s.

An SM clock cap is what prevents bus drops. Before the cap existed, back-to-back `llama-bench` runs
at 140 W took the card to 94 °C, and it fell off the bus (Xid 79). Stopping the server does
nothing for load that runs outside it.

## For P40 owners

- At 125 W, keep the card under about 65 °C under load; above that it loses clock steadily.
  Prefill-heavy work, such as long prompts on a dense model, is what gets it there.
- Force P8 when idle, and trigger it from your server's own activity, not from pstated's load
  detection.
- When you see 544 MHz, check the memory clock. A 544 MHz SM clock with 405 MHz memory is P8;
  with 3615 MHz memory it is a thermal cap.

## Files

- `analyze.py` joins a 30 s `nvidia-smi` CSV with llama-server `--log-file -lv 4` timing lines.
  Standard library only; run `python3 analyze.py --help` for usage.
- `speed_by_temp.csv`, `busy_clock_by_temp.csv` and `idle_by_pstate.csv` hold the aggregate
  tables above.

Related llama.cpp discussion: https://github.com/ggml-org/llama.cpp/discussions/8084
