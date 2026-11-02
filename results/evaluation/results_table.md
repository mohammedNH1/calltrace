| Check | Result | Sample | Compared against |
|---|---|---|---|
| Transcription: pooled WER | 9.32% | 19,248 reference words, 28 channels, 14 calls | Manual reference |
| Transcription: median call WER (range) | 6.81% (3.28-22.77%) | 14 calls | Manual reference |
| Transcription: agent / customer pooled WER | 5.79% / 15.04% | 28 channels | Manual reference |
| Speakers: median DER (channel-based) | 10.23% | 14 calls, 0.25 s collar | Manual segments |
| Speakers: median DER, word-level spans (channel-based) | 10.16% | 14 calls, pauses excluded | Manual segments |
| Speakers: median / max confusion (channel-based, turn spans) | 0.14% / 1.1% | 14 calls | Manual segments |
| Speakers: mono diarization baseline, median DER; median / max confusion | 6.97%; 1.1% / 35.23% | 14 calls, clusters mapped with the reference | Manual segments |
| Citations: calls passing all mechanical checks | 11 of 14 | 275 citations | Automatic validator |
| Grounding: claims fully supported by cited turns | 20 of 42 | partial 22, unsupported 0 | AI-assisted audit, not human |
| Grounding: claims correct against the whole call | 34 of 42 | partly 7, wrong 1 | AI-assisted audit, not human |
| Sentiment: overall / beginning / ending agreement | 8 / 13 / 12 of 14 | second reader saw model labels first | AI second reader, not human |
| Sentiment: agreement with human labels | Not available | 0 labels completed | Human worksheet pending |
| ASR vs reference: labels unchanged | 20 of 25 | 5 calls, 5 label fields per call | Same analysis settings |
