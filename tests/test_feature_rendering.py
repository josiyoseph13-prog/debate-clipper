import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from dc.core.config import load_config
from dc.core.hashing import content_hash
from dc.core.process import run_process
from dc.core.tools import find_tool,require_tool
from dc.ingest import ingest,ffprobe
from dc.renderer import make_render_plan,render
from dc.polish import apply_polish
from dc.timeline import runtime_plan


@unittest.skipUnless(find_tool("ffmpeg") and find_tool("ffprobe") and importlib.util.find_spec("cv2") and importlib.util.find_spec("PIL"),"FFmpeg image rendering dependencies unavailable")
class FeatureRenderingTests(unittest.TestCase):
    def test_optional_emoji_pop_raster_disappears_after_its_interval(self):
        import numpy as np
        from PIL import Image
        from dc.craft import prepare_emoji_pops
        with tempfile.TemporaryDirectory(prefix="emoji pop render ") as folder:
            work=Path(folder)
            source_path=work/"source.mp4"
            run_process([require_tool("ffmpeg"),"-hide_banner","-loglevel","error","-y","-f","lavfi","-i","color=c=navy:s=320x180:r=25:d=2","-c:v","libx264",source_path],timeout=30)
            cfg=load_config(overrides={"output":{"preset":"ultrafast"},"craft":{"emoji_pops":{"enabled":True}}})
            source=ingest(source_path,work,rights_class="own",rights_note="Synthetic fixture")
            plan=make_render_plan(source,{"id":"c_emoji","start":0,"end":2,"hook":{"headline_options":["College"]}},cfg,work)
            plan["transcript"]={"words":[{"text":"College","start":.2,"end":.8}]}
            manifest=prepare_emoji_pops(plan,plan["transcript"],cfg,work)
            self.assertEqual(len(manifest["items"]),1)
            render(plan,cfg,work,work/"clip.mp4")
            frames=[]
            x,y,w,h=manifest["items"][0]["box"]
            for time in (.5,1.5):
                target=work/f"sample{time}.png"
                run_process([require_tool("ffmpeg"),"-hide_banner","-loglevel","error","-y","-ss",str(time),"-i",work/"clip.mp4","-frames:v","1",target],timeout=30)
                with Image.open(target) as image:frames.append(np.array(image.crop((x,y,x+w,y+h)).convert("RGB"),dtype=float))
            self.assertGreater(np.abs(frames[0]-frames[1]).mean(),10)

    def test_lossless_headline_variants_have_one_final_encode_and_independent_chrome(self):
        from dc.variants import render_variants
        with tempfile.TemporaryDirectory(prefix="variant render ") as folder:
            work=Path(folder)
            source_path=work/"source.mp4"
            run_process([require_tool("ffmpeg"),"-hide_banner","-loglevel","error","-y","-f","lavfi","-i","testsrc2=s=320x180:r=25:d=1","-c:v","libx264",source_path],timeout=30)
            source=ingest(source_path,work,rights_class="own",rights_note="Synthetic fixture")
            cfg=load_config(overrides={"output":{"preset":"ultrafast"}})
            candidate={"id":"c_variant","start":0,"end":1,"text":"Hello","hook":{"headline_options":["Hello","Hello question"]}}
            plan=make_render_plan(source,candidate,cfg,work)
            plan.update({"transcript":{"words":[{"text":"Hello","start":.1,"end":.6}]},"cache_variants":True,"captions_ass":str(work/"captions.ass"),"caption_plan":str(work/"captions_plan.json")})
            render(plan,cfg,work,work/"clip.mp4")
            variants=render_variants(plan,plan,candidate,cfg,work,2)
            self.assertEqual(len(variants),2)
            self.assertTrue(all(row["status"]!="failed" and row["generation_loss"]=="one_final_h264_encode" for row in variants))
            self.assertNotEqual(content_hash(work/"variants"/"v1"/"chrome.png"),content_hash(work/"variants"/"v2"/"chrome.png"))

    def test_licensed_music_and_sfx_mix_without_changing_sample_rate_or_duration(self):
        with tempfile.TemporaryDirectory(prefix="licensed audio render ") as folder:
            work=Path(folder)
            source_path=work/"source.mp4"
            music=work/"synthetic music.wav"
            run_process([require_tool("ffmpeg"),"-hide_banner","-loglevel","error","-y","-f","lavfi","-i","testsrc2=s=320x180:r=25:d=2","-f","lavfi","-i","sine=frequency=440:sample_rate=48000:duration=2","-c:v","libx264","-c:a","aac","-shortest",source_path],timeout=30)
            run_process([require_tool("ffmpeg"),"-hide_banner","-loglevel","error","-y","-f","lavfi","-i","sine=frequency=220:sample_rate=48000:duration=2",music],timeout=30)
            cfg=load_config(overrides={"output":{"preset":"ultrafast"},"audio":{"music_file":str(music),"music_licensed":True,"sfx_file":str(music),"sfx_licensed":True}})
            source=ingest(source_path,work,rights_class="own",rights_note="Synthetic fixture")
            plan=make_render_plan(source,{"id":"c_audio","start":0,"end":2,"hook":{"headline_options":["Audio fixture"]}},cfg,work)
            render(plan,cfg,work,work/"clip.mp4")
            probe=ffprobe(work/"clip.mp4")
            self.assertEqual(next(row for row in probe["streams"] if row["codec_type"]=="audio")["sample_rate"],"48000")
            self.assertAlmostEqual(float(probe["format"]["duration"]),2,delta=.1)

    def test_timed_evidence_card_disappears_and_progress_advances(self):
        from PIL import Image
        import numpy as np
        with tempfile.TemporaryDirectory(prefix="craft render ") as folder:
            work=Path(folder)
            source_path=work/"source.mp4"
            run_process([require_tool("ffmpeg"),"-hide_banner","-loglevel","error","-y","-f","lavfi","-i","color=c=blue:s=320x180:r=25:d=3","-c:v","libx264",source_path],timeout=30)
            config=load_config(overrides={"output":{"preset":"ultrafast"},"polish":{"progress_bar":{"enabled":True}}})
            source=ingest(source_path,work,rights_class="own",rights_note="Synthetic fixture")
            candidate={"id":"c_card","start":0,"end":3,"hook":{"headline_options":["Card test"]},"evidence_card":{"text":"90%","start":.3,"end":1.1,"tag":"CLAIMED BY SPEAKER"}}
            plan=make_render_plan(source,candidate,config,work)
            plan["transcript"]={"words":[{"text":"90%","start":.3,"end":.9}]}
            render(plan,config,work,work/"clip.mp4")
            frames=[]
            for time in (.7,2):
                image=work/f"frame_{time}.png"
                run_process([require_tool("ffmpeg"),"-hide_banner","-loglevel","error","-y","-ss",str(time),"-i",work/"clip.mp4","-frames:v","1",image],timeout=30)
                with Image.open(image) as opened:frames.append(np.asarray(opened.convert("RGB")))
            feed=config.regions["feed"]
            region=(slice(feed["y"]+200,feed["y"]+350),slice(40,400))
            self.assertGreater(float(np.abs(frames[0][region].astype(float)-frames[1][region].astype(float)).mean()),5)
            bar_y=config.get("polish","progress_bar","y")
            red_counts=[int(((frame[bar_y:bar_y+6,:,0]>180)&(frame[bar_y:bar_y+6,:,1]<80)).sum()) for frame in frames]
            self.assertGreater(red_counts[1],red_counts[0])

    def test_silence_edit_is_rendered_without_removing_any_words(self):
        with tempfile.TemporaryDirectory(prefix="edited render ") as folder:
            work=Path(folder)
            source_path=work/"source.mp4"
            run_process([require_tool("ffmpeg"),"-hide_banner","-loglevel","error","-y","-f","lavfi","-i","testsrc2=s=320x180:r=25:d=12","-f","lavfi","-i","sine=frequency=440:sample_rate=48000:duration=12","-c:v","libx264","-c:a","aac","-shortest",source_path],timeout=30)
            config=load_config(overrides={"output":{"preset":"ultrafast"},"polish":{"tight_cut":{"enabled":True}}})
            source=ingest(source_path,work,rights_class="own",rights_note="Synthetic fixture")
            transcript={"segments":[{"text":"First. Last.","start":0,"end":11.5,"speaker":"a","words":[{"text":"First.","start":.1,"end":1,"speaker":"a"},{"text":"Last.","start":2.5,"end":11.5,"speaker":"a"}]}]}
            candidate={"id":"c_edit","start":0,"end":12,"hook":{"headline_options":["Edit test"]}}
            plan=make_render_plan(source,candidate,config,work)
            plan["transcript"]=transcript
            polish=apply_polish(plan,transcript,config)
            self.assertTrue(polish["tight_cut"])
            result=render(plan,config,work,work/"clip.mp4")
            runtime=json.loads((work/"runtime_plan.json").read_text())
            self.assertEqual([word["text"] for word in runtime["transcript"]["words"]],["First.","Last."])
            self.assertAlmostEqual(float(ffprobe(work/"clip.mp4")["format"]["duration"]),10.85,delta=.1)

    def test_three_caption_modes_and_fast_glow_execute_real_filter_graphs(self):
        with tempfile.TemporaryDirectory(prefix="caption mode render ") as folder:
            work=Path(folder)
            source_path=work/"source.mp4"
            run_process([require_tool("ffmpeg"),"-hide_banner","-loglevel","error","-y","-f","lavfi","-i","color=c=navy:s=320x180:r=25:d=1","-c:v","libx264",source_path],timeout=30)
            source=ingest(source_path,work,rights_class="own",rights_note="Synthetic fixture")
            for mode,method in (("gravitas","ass_layers"),("karaoke_lite","ass_layers"),("hormozi_glow","fast_glow")):
                cfg=load_config(overrides={"output":{"preset":"ultrafast"},"craft":{"caption_mode":mode},"captions":{"glow":{"method":method}}})
                plan=make_render_plan(source,{"id":"c_modes","start":0,"end":1,"hook":{"headline_options":["Mode test"]}},cfg,work)
                plan["transcript"]={"words":[{"text":"Hello","start":.1,"end":.8}]}
                output=work/(mode+".mp4")
                render(plan,cfg,work,output)
                self.assertGreater(output.stat().st_size,0)
                self.assertEqual(next(row for row in ffprobe(output)["streams"] if row["codec_type"]=="video")["avg_frame_rate"],"25/1")
