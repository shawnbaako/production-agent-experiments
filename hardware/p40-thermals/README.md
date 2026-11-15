# Tesla P40 at 125 W in a desktop: speed vs temperature, ten weeks of logs

Numbers from one P40 serving a dense 27B model around the clock. Nothing below was run for this note. It is a 30 s `nvidia-smi` sampler (about 190k rows, 2026-09-03 to 2026-11-15) joined with llama-server's own `print_timing` lines.

## Setup

- Tesla P40 24 GB, passive heatsink, open desktop case with extra case fans, no server airflow. Host is an i7-6700K, PCIe 3.0 x16.
- Power limit **125 W** (`nvidia-smi -pl 125`, the card's minimum; default is 250 W). Driver 580.178.04.
- llama.cpp upstream commit `34af94cd9` (2026-08-17), CUDA 12.9, `sm_61`, `GGML_CUDA_FORCE_MMQ=ON`, CUDA graphs on.
- Model: Qwen3.8-27B IQ4_XS, `-ngl 999 -fa on -c 131072 -ctk q8_0 -ctv q8_0 -np 1`, MTP draft (`--spec-type draft-mtp --spec-draft-n-max 4 --spec-draft-p-min 0.75`). Median draft acceptance 0.83.

## Speed by GPU temperature (82 logged requests)

Requests from a 38-hour window with trace logging on, mostly a recurring ~12k-token prompt. Temperature is the highest sample during that phase.

| Phase | Temp °C | n | Median tok/s | Median tokens | SM MHz |
|---|---|---:|---:|---:|---:|
| prefill | 45-49 | 34 | 186.1 | 12,073 | 1215 |
| prefill | 50-54 | 42 | 185.8 | 12,072 | 1202 |
| prefill | 60-64 | 3 | 181.9 | 12,074 | 1177 |
| decode | 50-54 | 34 | 16.2 | 245 | 1265 |
| decode | 55-59 | 22 | 16.2 | 243 | 1258 |
| decode | 60-64 | 3 | 15.9 | 185 | 1227 |

Below 65 °C the speed is flat: about 186 tok/s prefill at 12k tokens, about 16 tok/s decode with MTP. None of the logged requests ran above 69 °C, so the next table uses the sampler alone.

## SM clock under load by temperature (all samples at ≥90% utilisation)

| Temp °C | Samples | Median SM MHz | SM at 544 MHz | Median power W |
|---|---:|---:|---:|---:|
| 40-44 | 266 | 1227 | 0% | 124.8 |
| 50-54 | 432 | 1240 | 0% | 122.5 |
| 60-64 | 282 | 1227 | 0% | 122.0 |
| 65-69 | 348 | 1202 | 0% | 121.1 |
| 70-74 | 348 | 1139 | 0% | 119.9 |
| 75-79 | 603 | 1126 | 0.7% | 119.5 |
| 80-84 | 777 | 1050 | 28% | 116.8 |
| 85-89 | 1145 | 544 | 92% | 91.2 |

What this shows:

1. **At 125 W the card never boosts near its 1531 MHz maximum.** It sits at 1227-1240 MHz up to about 65 °C, pinned at the power limit.
2. **The clock starts falling at about 70 °C, with power still at the limit.** Excluding the 544 MHz samples, the median under load is 1202 MHz at 65-69 °C, 1139 at 70-74, 1075 at 80-84 and 1025 at 85-89. That is 17% below the cool clock before any software cap, and well before the card's 92 °C hardware slowdown.
3. **Above 84 °C our watchdog takes over** (next section), so the 85-89 °C row mostly shows the watchdog's cap, not the card's own behaviour. The highest sample in ten weeks was 89 °C.

## What the watchdog and the idle downclock do

A 20 s systemd timer reads temperature and utilisation:

- **80 °C**: log a warning.
- **84 °C**: `nvidia-smi -ac 3615,544`. This keeps memory at full clock and caps SM at 544 MHz. Power drops from about 120 W to 82-92 W, but under sustained load the card still heats. A typical trip: 81 °C, then 85 °C 51 s later, then 88 °C two minutes after the cap.
- **88 °C**: stop the server. Restart at 72 °C, lift the cap at 74 °C. The median stop-to-restart gap was 140 s.
- **Idle**: after about 3 minutes at 0% utilisation (60 s when warm), run `nvidia-pstated` so the card drops to real P8 with the model still loaded. An inotify watch on the llama-server log stops it on the next request. We only run pstated while idle because its own load detection left the card at P8 under 100% utilisation.

The idle downclock matters more than anything else here:

| Idle state (0% util) | Samples | Median °C | p90 °C | Median W |
|---|---:|---:|---:|---:|
| P8 via pstated | 167,906 | 31 | 40 | 11.0 |
| P0, model resident | 16,102 | 60 | 74 | 55.5 |

Idling at P0 at 55 W, the card starts every burst at 60-74 °C and reaches the 80s within one long prefill. At P8 it idles at 31 °C. Before the cap and idle tiers existed, with pstated stopped and the limit at 140 W, back-to-back `llama-bench` runs outside the server took the card to 94 °C, and it dropped off the bus (Xid 79). Stopping the server does nothing for load that runs outside it. The SM cap does.

In September, when this card ran every request, 7.8% of samples were at ≥90% utilisation and the watchdog stopped the server 323 times. In October we moved most traffic off the card and that share fell to 0.15%, with one stop. That drop came from the lighter workload. The cooling did not change.

## Takeaways for P40 owners

- In a desktop at the minimum 125 W limit, expect about 1230 MHz under load until about 65 °C, losing about 15% by the low 80s. Prefill-heavy work, such as long prompts on a dense model, is what gets you there.
- Run pstated (or an equivalent) only while idle and drive it from your own load signal. The idle temperature drops from 60 °C to 31 °C, which gives you room before throttling on the next burst.
- When you see 544 MHz, check the memory clock. 544 SM with 405 memory is P8 (pstate); 544 SM with 3615 memory is a thermal cap.

## Files

- `analyze.py`: joins a 30 s `nvidia-smi` CSV with llama-server `--log-file -lv 4` timing lines. Standard library only; `python3 analyze.py --help`.
- `speed_by_temp.csv`, `busy_clock_by_temp.csv`, `idle_by_pstate.csv`: the aggregate tables above.

Related llama.cpp discussion: https://github.com/ggml-org/llama.cpp/discussions/8084
