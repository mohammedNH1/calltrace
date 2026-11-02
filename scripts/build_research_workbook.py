"""Build reports/research_survey.xlsx from the verified research notes below.

Every fact was checked on the source page on the access date. Anything the source does
not state is marked "Unknown" or "Not stated" instead of being estimated.
"""

from __future__ import annotations

from collections import Counter

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from calltrace.config import load_config
from calltrace.data import AppTekDataset

ACCESSED = "2026-11-02"
FONT = "Arial"
TEAL, CHARCOAL, PALE, GOOD, BAD = "0F766E", "1F2937", "F0FDFA", "D1FAE5", "FEE2E2"
THIN = Side(style="thin", color="D1D5DB")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)

DATASET_COLUMNS = [
    "ID", "Source", "Link", "Language", "Data type", "Number of calls", "Audio duration (where known)",
    "Audio availability", "Transcript availability", "Speaker labels", "License / usage conditions",
    "Real or synthetic origin", "Domain relevance", "Accessibility", "Reviewer can reproduce access?",
    "Advantages", "Limitations", "Recommendation",
]

DATASETS = [
    ["D1", "AppTek Call-Center Dialogues (AppTek.ai; Beck et al., 2026)",
     "https://huggingface.co/datasets/apptek-com/apptek_callcenter_dialogues",
     "English, 14 accent groups", "Audio + manual transcripts", "873 calls (1,746 channel files)",
     "128.6 h of annotated speech; 151.1 h of total recording time (card and metadata)",
     "Yes. 16 kHz WAV, one speaker per file, plus a merged file per call",
     "Yes. Fully manual, with timed segments in the diarization config",
     "Yes. Agent/customer role and pseudonymous speaker ID on every channel and segment",
     "CC BY-SA 4.0. Card: intended for evaluation and analysis, not for training ASR or foundation models",
     "Human speech, role-played, unscripted. NOT real customer calls; names and details are fictional",
     "High. Agent-customer dialogues in 16 service domains",
     "Open. No login or gating. Single files can be downloaded", "Yes, at a pinned commit",
     "Separate channels give reliable speaker separation; manual references allow WER and DER; clear license; "
     "per-file download keeps the footprint small",
     "Role-played, so sentiment is likely milder than in real complaints; speakers may lack domain knowledge "
     "(stated in the paper); some files contain a spoken recording slate; gender imbalance across accents",
     "SELECTED"],
    ["D2", "SpokenWOZ (Si et al., NeurIPS 2023)",
     "https://spokenwoz.github.io/", "English (participants in Canada, Singapore, China, South Africa)",
     "Audio + transcripts + dialogue-state annotations", "5,700 dialogues", "249 h",
     "Yes. Two-track, 8 kHz; test archive 2.18 GB, train/dev archive 10.34 GB",
     "Partial. ASR-generated. Paper: agent text was corrected by annotators; user text keeps ASR noise on purpose",
     "Yes. user/system tag on each turn, with word timestamps",
     "CC BY-NC 4.0 (project page)",
     "Human speech by paid participants, role-played from template-generated task goals",
     "Medium. Agent-user task dialogues (booking and information), not general customer service",
     "Open on Hugging Face, whole archives only", "Yes, but needs a multi-GB archive",
     "Large; two tracks; rich annotation for task-oriented dialogue",
     "No clean customer-side reference, so customer WER cannot be measured; template goals limit natural complaints; "
     "8 kHz; no sentiment labels",
     "Runner-up. Best alternative if channel audio with larger scale matters more than clean references"],
    ["D3", "CallCenterEN (AIxBlock; Dao et al., 2025)",
     "https://huggingface.co/datasets/AIxBlock/92k-real-world-call-center-scripts-english",
     "English (Indian, American, Filipino accents)", "Transcripts only", "91,706 conversations",
     "10,448 audio hours (paper); about 10,500 (card). Audio not released",
     "No. Paper: audio withheld for biometric privacy reasons",
     "Yes. Machine-generated (AssemblyAI) with word timestamps; PII redacted",
     "Not stated on the card sections checked; speaker labelling not verified",
     "CC BY-NC 4.0 tag; card: research and model development only, no commercial use, resale, or redistribution",
     "Real calls", "High", "Open", "Yes for transcripts",
     "Largest open real call-center text resource found; useful for prompt development",
     "No audio, so it cannot support a transcription task",
     "Rejected: fails the audio requirement"],
    ["D4", "AxonData contact-center samples (English and multilingual cards)",
     "https://huggingface.co/datasets/AxonData/english-contact-center-audio-dataset",
     "English; multilingual card covers 7 languages", "Audio + transcripts (DOCX)",
     "Open sample: 2 English calls; multilingual sample: 11 calls. Full data (advertised 1,000+ h) is paid",
     "Full: 1,000+ h and 10,000 h advertised (not verified). Sample: about 2.8 MB and 13 MB",
     "Sample only. Mono MP3 from 8 kHz telephone speech",
     "Sample only (DOCX). Multilingual card also mentions concise summaries",
     "Card: automatic, machine-generated agent/customer labels",
     "CC BY-NC 4.0 tag on the sample; full data needs a commercial agreement",
     "Vendor states real-world recordings; provenance and consent not documented on the card", "High",
     "Sample open; full version paid", "Sample only",
     "Real-world telephone conditions", "Too few English calls; mono audio needs diarization; machine-made labels; "
     "consent details not visible",
     "Rejected: fewer than 10 usable English calls openly available"],
    ["D5", "UniData call-center-audio preview",
     "https://huggingface.co/datasets/UniDataPro/call-center-audio",
     "Multiple, including English (card)", "Audio + time-stamped transcripts in metadata",
     "Open preview: 5 FLAC calls. Full data (13,000+ h advertised) is paid", "Full: 13,000+ h advertised (not verified)",
     "Preview only", "Yes, in metainfo.csv of the preview",
     "Speaker tags in transcript text",
     "CC BY-NC-ND 4.0 tag (no derivatives); full data needs purchase",
     "Vendor states real conversations. Preview metadata names companies and the user's city and state",
     "High", "Preview open; full version paid", "Preview only",
     "Real, recent phone calls with timestamps",
     "Too few calls; ND term conflicts with publishing derived transcripts; preview shows named companies and user "
     "location, a privacy concern for a public repository",
     "Rejected: too small, derivative restriction, and responsible-use concern"],
    ["D6", "InfoBayAI Arabic Call Center Audio (dual channel)",
     "https://huggingface.co/datasets/InfoBayAI/Arabic_Call_Center_Audio_Dataset_Dual_Channel",
     "Arabic", "Audio; transcript availability Unknown (card is gated)",
     "Open listing shows 6 WAV files in sample folders (3 samples by file count). Full size Unknown", "Unknown",
     "Gated: contact details must be shared first", "Unknown", "Dual channel by name (SPEAKER_00 / SPEAKER_01 files)",
     "CC BY 4.0 tag on the sample; card and terms not readable without accepting the gate",
     "Unknown (file names suggest PII-processed audio)", "High, and relevant to Arabic-speaking markets",
     "Gated: not accessed for this project", "Requires accepting conditions",
     "Arabic dual-channel call audio is rare", "Too few samples; terms unread; references unknown",
     "Rejected: gated and too small. Worth revisiting for Arabic work"],
    ["D7", "Nakulbh/call-center-dataset",
     "https://huggingface.co/datasets/Nakulbh/call-center-dataset", "Unknown (no card)", "Audio",
     "20 WAV files in agent/customer folders, implying 10 calls", "Unknown", "Yes, split agent/customer files",
     "None found", "Folder names only (agent / customer)", "Not stated: no license and no README found",
     "Unknown", "Unknown without listening", "Open", "Yes, technically",
     "Split channels", "No license or provenance, so permitted use cannot be established; could hold real customer data",
     "Rejected: no permitted use, possible private recordings"],
    ["D8", "AIxBlock Japanese human-to-machine call-center audio",
     "https://huggingface.co/datasets/AIxBlock/Human-to-machine-Japanese-audio-call-center-conversations",
     "Japanese", "Audio", "Unknown", "Unknown (repository listing is about 19.4 GB)", "Yes", "Not stated on the card",
     "Stereo stated; label format Not stated", "CC BY-NC 4.0",
     "Card calls the audio synthetic but also describes native human speakers; the machine agent is scripted",
     "Low: human-to-machine, not customer to human agent", "Open, large zips", "Yes, with a large download",
     "Real speakers with a voice-bot pattern", "Wrong language and interaction type for this assessment",
     "Rejected: not human agent-customer speech"],
    ["D9", "Arabic call-domain ASR benchmark (Obaidah et al., 2024)",
     "https://arxiv.org/abs/2403.04280", "Arabic (6 dialect regions, speakers from 13 countries)",
     "Audio + manual transcripts (per paper)", "Not stated in the sections reviewed", "Not stated in the sections reviewed",
     "16 kHz mono per paper. No public download located", "Manual (41 annotators, 13 reviewers) per paper",
     "Not verified", "Not stated: no data license located",
     "Real calls from a communications company, with user consent per paper", "High, and relevant to Arabic markets",
     "Not publicly located", "No", "Relevant real data with manual references",
     "No download found, so results could not be reproduced by a reviewer",
     "Rejected: not accessible. Used as related work only"],
    ["D10", "Switchboard-1 Release 2 and CALLHOME American English (LDC)",
     "https://catalog.ldc.upenn.edu/LDC97S62", "English",
     "Audio + transcripts", "About 2,400 (Switchboard); 120 (CALLHOME)", "About 260 h; about 56 h",
     "Yes, for LDC licensees. 2-channel, 8 kHz", "Yes", "Two-channel telephone sides",
     "LDC user agreement; paid or membership access", "Real phone conversations",
     "Low: strangers or family and friends, not service calls", "Licensed", "No, without an LDC license",
     "Classic two-channel telephone corpora", "Not customer-agent; not freely reproducible",
     "Rejected: not relevant and restricted"],
]

GATES = [
    # id, audio accessible without purchase/gate, clear permitted use, >=10 customer-agent calls, responsible use
    ["D1", "Pass", "Pass", "Pass", "Pass", "Eligible"],
    ["D2", "Pass", "Pass", "Pass", "Pass", "Eligible"],
    ["D3", "FAIL: no audio", "Pass", "Pass", "Pass", "Not eligible"],
    ["D4", "Pass (sample)", "Pass (sample)", "FAIL: 2 English calls", "Unclear: consent not documented", "Not eligible"],
    ["D5", "Pass (preview)", "FAIL: no derivatives", "FAIL: 5 calls", "FAIL: named companies, user location", "Not eligible"],
    ["D6", "FAIL: gated", "Unclear: terms unread", "FAIL: about 3 calls", "Unknown", "Not eligible"],
    ["D7", "Pass", "FAIL: no license", "Unclear: content unknown", "FAIL: provenance unknown", "Not eligible"],
    ["D8", "Pass", "Pass", "FAIL: human-to-machine", "Pass", "Not eligible"],
    ["D9", "FAIL: not located", "FAIL: not located", "Unknown", "Pass per paper", "Not eligible"],
    ["D10", "FAIL: licensed", "Pass (under license)", "FAIL: not service calls", "Pass", "Not eligible"],
]

CRITERIA = [
    # criterion, weight, D1 score, D2 score, reason
    ["Customer-agent relevance", 20, 5, 3,
     "D1: free-form agent-customer calls in 16 service domains. D2: template-goal booking and information tasks."],
    ["Usable speaker separation", 20, 5, 4,
     "D1: one file per speaker plus role metadata. D2: two tracks and turn tags, at 8 kHz."],
    ["Reference annotations for evaluation", 20, 5, 2,
     "D1: manual references for both speakers with timed segments and a scoring script. D2: user side keeps ASR noise."],
    ["Clear permitted use", 15, 5, 4,
     "D1: CC BY-SA allows sharing with attribution. D2: CC BY-NC is fine here but narrower."],
    ["Reproducible access", 10, 5, 3, "D1: single files at a pinned commit. D2: whole multi-GB archive needed."],
    ["Manageable download and compute", 10, 5, 4, "D1: about 1 GB for the sample. D2: at least 2.18 GB; short dialogues."],
    ["Closeness to real calls", 5, 3, 2,
     "Neither is real. D1: unscripted with a chosen scenario. D2: scripted task goals. Scored low on purpose."],
]

PAPERS = [
    ["P1", "Beck et al. (2026). AppTek Call-Center Dialogues: A Multi-Accent Long-Form Benchmark for English ASR.",
     "https://arxiv.org/abs/2604.27543", "Paper + dataset card",
     "Evaluates open ASR models on the selected data across accents and segmentation methods. "
     "Parakeet v3: 9.2% WER; Whisper Large v3: 15.0% (Silero segmentation, all accents).",
     "Chose Parakeet v3 and Silero settings; adopted the dataset's WER protocol; the published average flagged our int8 "
     "run as abnormal (14.39% vs 9.2%), which led to switching to full-precision weights (9.32%).", "Published figures cover all 873 calls. Our 14-call sample is not a replication."],
    ["P2", "Si et al. (2023). SpokenWOZ: A Large-Scale Speech-Text Benchmark for Spoken Task-Oriented Dialogue Agents. NeurIPS.",
     "https://arxiv.org/abs/2305.13040", "Paper",
     "Describes the main alternative dataset and spoken phenomena such as backchannels and incomplete utterances.",
     "Runner-up in selection. Its backchannel discussion motivated separate backchannel handling in turn building.",
     "Keeps ASR noise on the user side by design, so it offers no clean customer reference."],
    ["P3", "Jia & SungChu (2020). A Deep Learning System for Sentiment Analysis of Service Calls.",
     "https://arxiv.org/abs/2004.10320", "Paper",
     "Studies sentiment in real service calls. States that whole-call sentiment tends to be robust to ASR errors while "
     "utterance-level analysis is sensitive, and that diarization errors can mislead sentiment patterns.",
     "Motivated the ASR-versus-reference experiment, the requirement for reliable speaker separation, and caution about "
     "single-turn evidence.", "Uses proprietary real calls and multimodal features; our method is text only."],
    ["P4", "Gao et al. (2023). Enabling Large Language Models to Generate Text with Citations. EMNLP.",
     "https://arxiv.org/abs/2305.14627", "Paper",
     "Proposes evaluating generated text by citation quality as well as correctness.",
     "Basis for separating 'citation exists' (mechanical check) from 'citation supports the claim' (grounding audit).",
     "Targets question answering over documents, not call transcripts."],
    ["P5", "Feigenblat et al. (2021). TWEETSUMM: A Dialog Summarization Dataset for Customer Service. Findings of EMNLP.",
     "https://arxiv.org/abs/2111.11894", "Paper",
     "Customer-care summaries focused on the customer's problem and the proposed solution.",
     "Supports the issue / action / outcome structure required by the assessment.",
     "Written chat dialogues, not speech; no ASR errors."],
    ["P6", "An empirical analysis of word error rate and keyword error rate. INTERSPEECH 2008 (IBM Research).",
     "https://research.ibm.com/publications/an-empirical-analysis-of-word-error-rate-and-keyword-error-rate",
     "Conference paper (abstract reviewed)",
     "Case study on 100 contact-center calls: keyword errors grow faster than WER on low-accuracy transcripts, yet two "
     "analytics tasks were not significantly affected.",
     "Reason to inspect which words are wrong (names, numbers), and to test downstream effects directly instead of relying on WER.",
     "Older ASR system; only the abstract was reviewed."],
    ["P7", "Ghosh et al. (2025). ASR-Synchronized Speaker-Role Diarization.",
     "https://arxiv.org/abs/2507.17765", "Paper",
     "Argues that speaker diarization and role diarization are different tasks.",
     "Supports keeping Speaker 1/2 separate from Customer/Agent and documenting how each is obtained.",
     "Learned role model on other domains; here roles come from metadata."],
]

SOURCES = [
    ["S1", "AppTek dataset card and metadata", DATASETS[0][2], "Dataset card, metadata files",
     "Counts, license, roles, fields, intended use; revision b98967d9946f7f59f58d08624a2a00fe98fe0219"],
    ["S2", "AppTek paper", "https://arxiv.org/abs/2604.27543", "Paper", "Collection method, tables 1-3, limitations"],
    ["S3", "AppTek score.py and word_mappings.py",
     "https://huggingface.co/datasets/apptek-com/apptek_callcenter_dialogues/blob/main/score.py", "Code", "WER protocol"],
    ["S4", "SpokenWOZ project page", DATASETS[1][2], "Project page", "License and download links"],
    ["S5", "SpokenWOZ paper", "https://arxiv.org/abs/2305.13040", "Paper", "Collection, ASR noise policy, two-track 8 kHz audio"],
    ["S6", "SpokenWOZ test files", "https://huggingface.co/datasets/ssz1111/SpokenWOZ-Test-Audio-Fixed", "Repository listing",
     "Archive sizes; 1,000 test dialogues; turn format"],
    ["S7", "CallCenterEN card", DATASETS[2][2], "Dataset card", "Counts, ASR source, license text"],
    ["S8", "CallCenterEN paper", "https://arxiv.org/abs/2507.02958", "Paper abstract", "Audio withheld for biometric privacy"],
    ["S9", "AxonData cards", DATASETS[3][2], "Dataset card, file listing", "Sample file counts, machine labels, paid full version"],
    ["S10", "AxonData multilingual card", "https://huggingface.co/datasets/AxonData/multilingual-call-center-speech-dataset",
     "Dataset card, file listing", "11 sample calls; mono 8 kHz"],
    ["S11", "UniData card and preview", DATASETS[4][2], "Dataset card, metainfo.csv", "License, file count, metadata columns"],
    ["S12", "InfoBayAI listing", DATASETS[5][2], "API file listing only (card gated)", "File names, license tag, gate status"],
    ["S13", "Nakulbh listing", DATASETS[6][2], "API file listing", "File count; absence of README and license"],
    ["S14", "AIxBlock Japanese card", DATASETS[7][2], "Dataset card", "Interaction type, license"],
    ["S15", "Arabic benchmark paper", DATASETS[8][2], "Paper", "Dataset description; no download located"],
    ["S16", "LDC Switchboard catalog", DATASETS[9][2], "Catalog page", "Size, license type"],
    ["S17", "LDC CALLHOME catalog", "https://catalog.ldc.upenn.edu/LDC97S42", "Catalog page", "Size, participants, license type"],
    ["S18", "Parakeet TDT 0.6B v3 model card", "https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3", "Model card", "CC BY 4.0"],
    ["S19", "Parakeet ONNX export", "https://huggingface.co/istupakov/parakeet-tdt-0.6b-v3-onnx", "Model card",
     "CC BY 4.0; revision 8f23f0c03c8761650bdb5b40aaf3e40d2c15f1ce"],
    ["S20", "Qwen3.5-4B GGUF", "https://huggingface.co/unsloth/Qwen3.5-4B-GGUF", "Model card",
     "Apache-2.0; revision e87f176479d0855a907a41277aca2f8ee7a09523"],
    ["S21", "llama.cpp release b12034", "https://github.com/ggml-org/llama.cpp/releases/tag/b12034", "Release page", "Windows Vulkan binary"],
]


def base_font(**kwargs) -> Font:
    return Font(name=FONT, size=kwargs.pop("size", 10), color=kwargs.pop("color", CHARCOAL), **kwargs)


def title(sheet, text: str, subtitle: str) -> int:
    sheet["A1"] = text
    sheet["A1"].font = base_font(size=14, bold=True, color=TEAL)
    sheet["A2"] = subtitle
    sheet["A2"].font = base_font(italic=True)
    sheet.sheet_view.showGridLines = False
    return 4


def write_table(sheet, top: int, headers: list[str], rows: list[list], widths: list[int] | None = None) -> int:
    """Write a formatted table and return the row after it."""
    for column, header in enumerate(headers, start=1):
        cell = sheet.cell(top, column, header)
        cell.font = base_font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor=TEAL)
        cell.alignment = Alignment(wrap_text=True, vertical="center", horizontal="center")
        cell.border = BORDER
    for row_index, row in enumerate(rows, start=top + 1):
        for column, value in enumerate(row, start=1):
            cell = sheet.cell(row_index, column, value)
            cell.font = base_font()
            cell.alignment = Alignment(wrap_text=True, vertical="top")
            cell.border = BORDER
            if isinstance(value, str) and value.startswith("http"):
                cell.hyperlink = value
                cell.font = base_font(color=TEAL, underline="single")
    if widths:
        for column, width in enumerate(widths, start=1):
            sheet.column_dimensions[get_column_letter(column)].width = width
    return top + len(rows) + 1


def lines_block(sheet, top: int, heading: str, lines: list[str], span: int = 6) -> int:
    sheet.cell(top, 1, heading).font = base_font(bold=True, size=11, color=TEAL)
    row = top + 1
    for line in lines:
        sheet.merge_cells(start_row=row, start_column=1, end_row=row, end_column=span)
        cell = sheet.cell(row, 1, line)
        cell.font = base_font()
        cell.alignment = Alignment(wrap_text=True, vertical="top")
        # Merged cells do not auto-fit, so the height is estimated from the text length.
        sheet.row_dimensions[row].height = 14 * (len(line) // 125 + 1) + 2
        row += 1
    return row + 1


def main() -> None:
    config = load_config()
    dataset = AppTekDataset(config)
    catalogue = dataset.build_catalogue()
    manifest = dataset.load_manifest()
    flipped = sum(record.channels["1"]["role"] == "customer" for record in catalogue)
    domains = Counter(record["domain"] for record in manifest["selected"])
    sampled_minutes = sum(record["duration_s"] for record in manifest["selected"]) / 60

    workbook = Workbook()

    # Sheet 1: dataset comparison.
    sheet = workbook.active
    sheet.title = "Dataset comparison"
    top = title(sheet, "Dataset comparison: public customer-agent voice data",
                f"All facts checked on source pages, accessed {ACCESSED}. Unknown or Not stated means the source does not say.")
    widths = [5, 28, 34, 18, 18, 24, 24, 26, 28, 24, 30, 28, 22, 18, 16, 34, 40, 26]
    end = write_table(sheet, top, DATASET_COLUMNS, DATASETS, widths)
    sheet.freeze_panes = sheet.cell(top + 1, 3)
    sheet.auto_filter.ref = f"A{top}:{get_column_letter(len(DATASET_COLUMNS))}{end - 1}"
    for row in range(top + 1, end):
        fill = PALE if sheet.cell(row, 18).value == "SELECTED" else None
        if fill:
            for column in range(1, len(DATASET_COLUMNS) + 1):
                sheet.cell(row, column).fill = PatternFill("solid", fgColor=fill)
    sheet.cell(end + 1, 1, "Mirrors of D1 on Hugging Face (for example hussxamg04/apptek_callcenter_dialogues) are ignored; "
               "the publisher's repository is the source.").font = base_font(italic=True)

    # Sheet 2: papers and articles.
    sheet = workbook.create_sheet("Papers and articles")
    top = title(sheet, "Papers and articles: what each contributes to this project",
                f"Accessed {ACCESSED}. Listed only where a source changed an implementation or evaluation decision.")
    end = write_table(
        sheet, top,
        ["ID", "Reference", "Link", "Type", "Relevant finding", "How it is used here", "Limits for this project"],
        PAPERS, [5, 46, 34, 16, 52, 52, 40],
    )
    sheet.freeze_panes = sheet.cell(top + 1, 3)

    # Sheet 3: selection decision.
    sheet = workbook.create_sheet("Selection decision")
    top = title(sheet, "Selection decision: AppTek Call-Center Dialogues (D1)",
                "Eligibility gates are applied first. Only eligible datasets receive a weighted score.")
    for column, width in zip("ABCDEF", (34, 24, 24, 26, 30, 14)):
        sheet.column_dimensions[column].width = width
    sheet.cell(top, 1, "Step 1. Eligibility gates (all must pass)").font = base_font(bold=True, size=11, color=TEAL)
    end = write_table(
        sheet, top + 1,
        ["Dataset", "Audio accessible (no purchase or gate)", "Permitted use is clear",
         "At least 10 customer-agent calls", "Responsible use", "Result"],
        GATES,
    )
    for row in range(top + 2, end):
        result = sheet.cell(row, 6)
        result.fill = PatternFill("solid", fgColor=GOOD if result.value == "Eligible" else BAD)
        result.font = base_font(bold=True)

    top = end + 1
    sheet.cell(top, 1, "Step 2. Weighted comparison of eligible datasets (scores 1-5; weights can be edited)").font = base_font(
        bold=True, size=11, color=TEAL)
    header_row = top + 1
    first = header_row + 1
    last = first + len(CRITERIA) - 1
    write_table(sheet, header_row, ["Criterion", "Weight", "D1 AppTek score", "D2 SpokenWOZ score", "Reason"],
                CRITERIA)
    sheet.merge_cells(start_row=header_row, start_column=5, end_row=header_row, end_column=6)
    for row in range(first, last + 1):
        sheet.merge_cells(start_row=row, start_column=5, end_row=row, end_column=6)
        sheet.row_dimensions[row].height = 54
        for column in "BCD":
            # Blue text marks judgment inputs that a reader may change.
            sheet[f"{column}{row}"].font = base_font(color="0000FF")
    labels = [
        ("Weight total (should be 100)", f"=SUM(B{first}:B{last})", None, None),
        ("Weighted score (out of 5)", None,
         f"=SUMPRODUCT($B{first}:$B{last},C{first}:C{last})/SUM($B{first}:$B{last})",
         f"=SUMPRODUCT($B{first}:$B{last},D{first}:D{last})/SUM($B{first}:$B{last})"),
        ("Sensitivity: equal weights", None, f"=AVERAGE(C{first}:C{last})", f"=AVERAGE(D{first}:D{last})"),
        ("Sensitivity: without the reference criterion", None,
         f"=(SUMPRODUCT($B{first}:$B{last},C{first}:C{last})-$B{first + 2}*C{first + 2})/(SUM($B{first}:$B{last})-$B{first + 2})",
         f"=(SUMPRODUCT($B{first}:$B{last},D{first}:D{last})-$B{first + 2}*D{first + 2})/(SUM($B{first}:$B{last})-$B{first + 2})"),
    ]
    row = last + 1
    for label, weight, d1, d2 in labels:
        sheet.cell(row, 1, label).font = base_font(bold=True)
        for column, value in ((2, weight), (3, d1), (4, d2)):
            cell = sheet.cell(row, column, value)
            cell.font = base_font(bold=True)
            cell.number_format = "0.00" if column > 2 else "0"
            cell.border = BORDER
        sheet.cell(row, 1).border = BORDER
        row += 1
    row = lines_block(sheet, row + 1, "Note on scores", [
        "Scores are the author's judgment against the stated reasons, not measurements. They are shown so that a reader can disagree with them.",
    ])

    row = lines_block(sheet, row, "Why D1 is better than the alternatives", [
        "Real public customer calls with audio were not found: real corpora either withhold audio (D3), sell it (D4, D5), or lack a usable license (D7, D9, D10).",
        "D1 is the only candidate with split channels, manual references for both speakers, timed reference segments, and a license that allows sharing derived results.",
        "SpokenWOZ (D2) is larger but keeps ASR noise in user text. That rules out customer-side WER, and customer speech is the focus of this assessment.",
    ])
    row = lines_block(sheet, row, "What cannot be concluded from D1 (stated prominently in the README and slides)", [
        "THE DATA IS ROLE-PLAYED, NOT REAL CUSTOMER CALLS. Results say nothing about real customers, real complaints, or business impact.",
        "Participants acted as customers and agents, so sentiment may be milder or staged. Sentiment findings describe language in these role-plays only.",
        "Audio came from VoIP on consumer devices with clean split channels. Mono telephone calls would be harder, and channel-based separation would not apply.",
        "Fourteen calls cannot support claims per accent or per domain. Accent-level WER is shown as a sanity check only.",
    ])
    row = lines_block(sheet, row, "Sampling rule and data-quality checks (executed)", [
        f"Rule: seed {manifest['seed']}; {manifest['rule']}. It uses metadata only, so calls cannot be chosen by how easy they are.",
        f"Sample: {len(manifest['selected'])} calls, {sampled_minutes:.0f} minutes, {len(domains)} distinct domains, one per accent. Eligible pool: {manifest['eligible_calls']} of {manifest['catalogue_calls']}; exclusions: {len(manifest['exclusions'])}.",
        f"Check: all {len(catalogue)} calls have two channels with exactly one agent and one customer role.",
        f"Check: channel 1 is the customer in {flipped} of {len(catalogue)} calls, so channel order must not be treated as role.",
        "Check: some recordings open with a spoken slate (for example a scenario name and number). It appears in the reference and is flagged as a quality note.",
        "Check: card totals differ (128.6 h vs 151.1 h). The paper explains that 128.6 h is annotated speech. Total recording time from metadata is 151.1 h.",
    ])
    row = lines_block(sheet, row, "Responsible use", [
        "License: CC BY-SA 4.0. Attribution is given in the README. Derived transcripts and summaries in results/ are shared under the same license.",
        "Audio is not committed to the repository, only downloaded by script at a pinned commit, to keep the repository small. The license would allow sharing it.",
        "The card excludes training use. This project only evaluates and analyses, and trains nothing.",
        "No private customer recording is used. Speakers were told to use fictional names and details.",
    ])

    # Sheet 4: source references.
    sheet = workbook.create_sheet("Source references")
    top = title(sheet, "Source references", f"All sources were opened on {ACCESSED}.")
    rows = [[*entry[:4], ACCESSED, entry[4]] for entry in SOURCES]
    write_table(sheet, top, ["ID", "Source", "Link", "Type", "Accessed", "Used to verify"], rows, [5, 34, 62, 26, 12, 60])
    sheet.freeze_panes = sheet.cell(top + 1, 1)

    path = config.path("reports") / "research_survey.xlsx"
    path.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(path)
    print(path)


if __name__ == "__main__":
    main()
