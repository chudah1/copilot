# penKeep TikTok carousels

This directory contains the first ten **Before Hindsight** carousel posts.

The operating plan for future evergreen and current-event content lives in
[`CONTENT_STRATEGY.md`](./CONTENT_STRATEGY.md).

## Render

From the repository root:

```bash
node content/tiktok/render.mjs
```

The renderer uses local system fonts and headless Chrome to create deterministic
1080×1920 PNG files. Finished posts and captions are written to `output/`.
Pass one or more post numbers to render only those posts, for example:

```bash
node content/tiktok/render.mjs 3 8
```

To refresh only the cover image for every post:

```bash
node content/tiktok/render.mjs --covers
```

## Video

Current-event thesis-test posts default to video — see the format
assignment in
[`CONTENT_STRATEGY.md`](./CONTENT_STRATEGY.md#format-assignment). Video
scripts and timing live in `videos.mjs`; the reusable scene renderer lives
in `video-scenes.mjs`; the visual chrome lives in `video-template.html`.

Render one or more videos by slug. The renderer requires Playwright and
FFmpeg:

```bash
PLAYWRIGHT_MODULE="file:///path/to/playwright/index.mjs" \
FFMPEG_PATH="/path/to/ffmpeg" \
node content/tiktok/render-video.mjs video-01-profitable-bad-decision
```

Omit the slug to render every video in `videos.mjs`.

Add a low-volume Commercial Sounds track inside TikTok instead of baking
copyrighted audio into the exported video.

## Publishing notes

- Upload slides in numeric order.
- Add quiet background music from TikTok's library.
- Keep TikTok's content-disclosure setting enabled on posts that directly promote
  penKeep.
- Check every post in TikTok's preview before publishing; interface overlays can
  vary by device and app version.
- The educational disclaimer is included in every caption. It does not replace
  a legal review of marketing or financial-promotion compliance.

## Content system

The layout reserves the lower portion of each image for TikTok's interface. Copy,
captions, hashtags, and slide structures live in `posts.mjs`; the reusable visual
system lives in `template.html`. The opening batch is intentionally published
under the audience-first **Before Hindsight** identity and contains no penKeep
promotion. `profile.html` produces the matching account avatar.

Video posts follow the same data/renderer split: copy, captions, hashtags,
and scene structures live in `videos.mjs`; the reusable scene renderer
lives in `video-scenes.mjs`; the visual chrome lives in
`video-template.html`.
