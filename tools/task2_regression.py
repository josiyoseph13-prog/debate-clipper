"""Re-export a Task 1 clip with Speaker Frame OFF and require byte identity."""
from pathlib import Path
from argparse import Namespace
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from dc.cli import command_render
from dc.core.io import atomic_copy,atomic_write_json
from dc.core.hashing import file_hash


def main():
    baseline=ROOT/"exports/2026-10-06_dei-is-a-sin-charlie-kirk-ends-debate-once-for-a/clip_02_but-my-question-is-how-can-christian-teaching-on-love_3m10s-3m38s_c_3b29c90cfa17_8521a1b4/02_but-my-question-is-how-can-christian-teaching-on-love.mp4"
    code=command_render(Namespace(job="job_863e97df620d",candidate="c_3b29c90cfa17",headline=None,layout="auto",variants=1,preset="political_lens",crop=None,debug_overlay=False,accept_review=False))
    output=ROOT/"reports/speaker_frame/without_speaker_frame.mp4"
    atomic_copy(ROOT/"work/job_863e97df620d/c_3b29c90cfa17.mp4",output)
    before,after=file_hash(baseline),file_hash(output)
    result={"baseline":str(baseline.relative_to(ROOT)),"output":str(output.relative_to(ROOT)),"baseline_sha256":before,"output_sha256":after,"returncode":code,"byte_identical":before==after,"passed":code==0 and before==after}
    atomic_write_json(ROOT/"reports/speaker_frame/no_feature_regression.json",result)
    print(result)
    return 0 if result["passed"] else 1


if __name__=="__main__":
    raise SystemExit(main())
