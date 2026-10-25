# alas-hires · High-resolution patch for Alas

[中文](README.md)

Runs [Alas](https://github.com/LmeSzinc/AzurLaneAutoScript) (the Azur Lane bot) on 2K/4K and other 16:9 emulator screens, so you no longer have to switch the emulator back to 1280x720 for the bot.

Alas officially supports 1280x720 only; its author has stated in [#4177](https://github.com/LmeSzinc/AzurLaneAutoScript/issues/4177) that other resolutions will not be supported. **This is a third-party, unofficial patch and is not affiliated with the Alas developers.**

## How it works

The patch is loaded at run time. It does not modify Alas's files or settings, so Alas keeps auto-updating as usual. At 1280x720 none of the hooks do anything and Alas behaves exactly as stock.

- **Screenshots** are downscaled to 1280x720 before Alas sees them, so Alas's templates, colour checks, OCR and map detection all keep working.
- **Clicks**: the ADB, uiautomator2 and MuMu `nemu_ipc` click methods use device pixels, so the patch scales them up. minitouch and MaaTouch already convert coordinates themselves and are left alone.
- **UI hierarchy coordinates** (the CN login agreement pop-up and the like) are scaled back to 720p.
- **Resolution check**: relaxed to accept any 16:9 screen.
- **Small text**: at high resolution the game renders small text with thinner, brighter strokes. After downscaling it no longer matches the original templates (e.g. the "Clear mode" title drops from 1.00 to 0.69). For such buttons the patch ships an alternative template cut from a 4K frame, tried only when the original fails.
- **Near-miss recording**: in hi-res mode, matches that fall just below the threshold are saved under `alas_hires\runs\` so you can add templates.
- **Screenshot method**: on MuMu, if Alas is configured with a slow method (uiautomator2, ADB, ...), this run uses `nemu_ipc` instead (about 40 ms per 4K frame vs. about 1.2 s for adb). Alas's own setting is not changed.

## Tested

Environment: MuMu Player 12 at 3840x2160; CN server; Alas as of October 2026; minitouch for clicks.

- **Screenshot scoring**: two rounds of about 140 frames each, comparing native 720p frames with 4K frames downscaled to 720p. Of 2716 buttons clearly detected at 720p, 12 were missed at 4K. Inspecting them one by one, the only genuine rendering differences were text buttons, which now have 4K templates. OCR readings (oil, coins, meowfficer level and capacity, OpSi action points, exercise count, guild exchange count, dorm food) were identical on both. OpSi map detection (grids, fleet position, globe positioning) was identical too.
- **Live runs**: daily use since 2026-10-20 covering commissions, tactical class, research, dorm, guild, rewards, shops, main/hard campaigns, events, dailies, awakening, ash beacon, OpSi exploration, obscure/abyssal/stronghold zones. The patch itself has not failed; every problem so far was one more text button unrecognised at 4K, fixed by adding a template (see "Known limitations"). One OpSi map-swipe loop was Alas's own bug [#5360](https://github.com/LmeSzinc/AzurLaneAutoScript/issues/5360), which also happens at 1280x720.

## Install

1. Download `alas-hires-v*.zip` from [Releases](../../releases) and extract it **into the folder that contains AzurLaneAutoScript**, next to it:

   ```text
   AlasApp\
   ├─ AzurLaneAutoScript\     ← Alas
   ├─ alas_hires\             ← the patch
   └─ AlasHires.bat
   ```

2. Set the emulator to a 16:9 resolution such as 3840x2160, 2560x1440 or 1920x1080, and restart it.
3. Double-click `AlasHires.bat`, pick a config in the AlasHires window and press **启动** (Start).
4. The patch is active when the "模拟器画面" (emulator screen) tile shows something like `3840x2160 ×3`, or the log contains:

   ```text
   ALAS-HIRES: device scale 3.000 (3840x2160 -> 1280x720)
   ```

With [daily-hub](https://github.com/sheinlee/daily-hub), put `..\alas_hires\run_alas.py` (relative to the AzurLaneAutoScript folder) in the Azur Lane "custom launch script" field. daily-hub 0.1.2 and later no longer treat an idle AlasHires window as "Alas already running".

To uninstall, delete `alas_hires\` and `AlasHires.bat` and go back to starting Alas from its own GUI.

## The AlasHires window

The window's labels are Chinese; here is what they do.

- Runs on Alas's bundled Python and shows its page in an Edge app window (a tiny server on 127.0.0.1, no network access; without Edge it opens in the default browser).
- **启动 / 停止 (Start / Stop)**: Alas runs as an independent process, so closing the window does not stop it; double-click `AlasHires.bat` again to see the running instance. Start is disabled while Alas's own GUI, daily-hub or a console is already running the scheduler; stopping an Alas started elsewhere asks for confirmation first.
- **调度 (Scheduler)**: the same running / pending / waiting lists as Alas's overview page, read live from Alas's config, priority table and translation file, so they follow Alas updates. Task settings are still edited in Alas's own GUI; both windows can stay open.
- **Status tiles**: current task, emulator screen and scale, screenshot method, number of 4K templates, near misses and warnings/errors; the log view can be filtered to highlights only.
- Without the window, running `toolkit\python.exe ..\alas_hires\run_alas.py alas` from the AzurLaneAutoScript folder does the same thing.

## Known limitations

- **4K text templates exist for the CN server only**, 12 of them: clear mode (2), auto search, the dangerous / safe / obscure / abyssal zone labels, siren stronghold, the shop's "supply shop" tab, the private quarters title, "dock empty", and the daily mission "quick battle" button. **The archive zone is still missing.** On other servers, or after the game changes its text, the corresponding button may not be recognised and you will need to add a template (see below). In practice almost everything missed at 4K is a text button, and each new kind of task may reveal one; when Alas gets stuck or requests a human takeover, look at the near-miss records in `alas_hires\runs\` first.
- Only tested on MuMu 12 at 3840x2160. 2560x1440 and 1920x1080 use the same scaling, but the text templates were cut from 4K frames and may not match there.
- A scheduler started from Alas's own GUI does not go through the patch and still stops at "Resolution not supported" on a hi-res screen.

## Adding 4K text templates

When a button is not recognised during a run, find its crop under `alas_hires\runs\<time>\near\` and run, from the AzurLaneAutoScript folder:

```bat
toolkit\python.exe ..\alas_hires\make_alt.py add --button os.ZONE_ARCHIVE --crop ..\alas_hires\runs\<time>\near\<file>.png
toolkit\python.exe ..\alas_hires\make_alt.py add --button handler.CLEAR_MODE_TITLE --shot <hi-res screenshot.png>
toolkit\python.exe ..\alas_hires\make_alt.py check --shots <folder of hi-res screenshots>
```

- The button name is `module.BUTTON`, as in Alas's `module/<module>/assets.py`.
- For other servers put `--server en`, `jp` or `tw` before the command.
- A running Alas re-reads the template manifest every 10 seconds, so new templates work without a restart.
- When an Alas update changes an original template, its 4K alternative is disabled automatically and the log says so.
- Text titles render slightly differently on different backgrounds (the event map's "clear mode" scores only 0.849 against the template cut from a main-campaign map). `make_alt.py similarity --button handler.CLEAR_MODE_TITLE 0.8` lowers the threshold for that button's 4K templates only; run `check` afterwards to make sure nothing else matches. The threshold never goes above Alas's own.
- Near-miss log lines and `near_miss.csv` carry both the original template's score and the best 4K template's score.

Environment variables:

- `ALAS_HIRES_SCREENSHOT=keep`: do not switch the screenshot method.
- `ALAS_HIRES_RUNS=<folder>`: write near-miss records elsewhere.

## Notes

- **This is an unofficial patch. Please do not report problems you hit while using it to the Alas repository or community.** Reproduce them first without the patch at 1280x720, then report them the way Alas asks.
- [Alas](https://github.com/LmeSzinc/AzurLaneAutoScript) is free, open-source software (GPL-3.0) by LmeSzinc and contributors. Please follow the [Alas community guidelines](https://github.com/LmeSzinc/AzurLaneAutoScript/discussions/1416).
- Automation may violate the game's terms of service; use at your own risk. This project is not affiliated with the game's publisher.
- The templates under `alas_hires\alt\` are crops of in-game text and remain the publisher's copyright.

## License

[GPL-3.0](LICENSE). The patch imports and replaces Alas's functions at run time and is therefore a derivative work of Alas, so it carries the same license.

Copyright (C) 2026 sheinlee
