# Artwork

`artwork.png` is an original AI-generated community illustration. `hero.png` is
the README header, `social-card.png` is a 1200 by 675 sharing image, and
`social-preview.png` is a 1280 by 640 GitHub social-preview export. None is an
official Hermes mascot, Nous Research asset, TypeSafe logo or endorsement.

Generated with OpenAI GPT Image 2, medium quality. The image was inspected for
legibility, anatomy, accidental branding and composition. Fine robot-finger and
display-card details are stylized. No performance claims appear in the artwork.
Only the artwork prompt, not repository contents or private records, was sent.

The image-generation provider did not expose a reliable per-image cost in the
returned receipt. No exact cost is asserted.

## Rebuild the title overlay

With optional Pillow installed in a separate environment:

```sh
python assets/render_banner.py --font /path/to/a/bold-font.ttf
```

The renderer performs no network calls. Font choice affects the output; inspect
it again after rendering. Pillow is not a plugin/runtime dependency. The source
image is stripped of ancillary metadata on export.

## Generation brief

Original premium anime/editorial-tech illustration for an unofficial Hermes
community context-engine experiment. Wide composition; dark charcoal and navy,
gold/amber and restrained cyan accents. Right half: an adult female software
engineer with silver-white short hair, small gold wing hair clips and a navy
jacket with gold edging. Beside her, a friendly geometric floating cyan-and-gold
robot sorts translucent information cards, retaining bright important cards and
moving obsolete dim ones to a local archive box. Left side: clean negative space
for a later title. Subtle orbital circuit, no logos, readable generated text,
watermarks, performance claims or official branding. Original fan-art character,
not a copied official mascot. The overlay reads "Hermes + Jev", "Selective
context. Measurable trade-offs." and "Experimental. Test before trusting."

See [NOTICE](../NOTICE) for rights and attribution.
