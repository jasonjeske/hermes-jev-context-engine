"""Rebuild the header from the original generated artwork. Optional dependency: Pillow.

Usage: python assets/render_banner.py [--font /path/to/bold.ttf]
No network requests, inference or environment/config access.
"""
from pathlib import Path
import argparse
from PIL import Image, ImageDraw, ImageFont


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--font', help='Optional bold TrueType/OpenType font')
    args = parser.parse_args()
    here = Path(__file__).resolve().parent
    image = Image.open(here / 'artwork.png').convert('RGB')
    image = image.resize((1672, 941), Image.Resampling.LANCZOS)
    draw = ImageDraw.Draw(image)
    def font(size):
        for candidate in (args.font, 'DejaVuSans-Bold.ttf', '/System/Library/Fonts/Helvetica.ttc'):
            if not candidate:
                continue
            try:
                return ImageFont.truetype(candidate, size)
            except OSError:
                pass
        return ImageFont.load_default(size=size)
    gold = '#EEC875'
    white = '#F4F0E6'
    muted = '#ACB8C5'
    draw.rounded_rectangle((86, 157, 478, 199), radius=9, outline='#76633D', width=1)
    draw.text((103, 165), 'AN EXPERIMENT FOR HERMES AGENT', fill=gold, font=font(18))
    draw.text((82, 231), 'Hermes', fill=white, font=font(91))
    draw.text((85, 337), '+ Jev', fill=gold, font=font(91))
    draw.text((89, 465), 'Selective context.', fill=white, font=font(34))
    draw.text((89, 511), 'Measurable trade-offs.', fill=white, font=font(34))
    draw.line((90, 591, 326, 591), fill=gold, width=2)
    draw.text((90, 622), 'Unofficial community plugin', fill=muted, font=font(22))
    draw.text((90, 654), 'Experimental. Test before trusting.', fill=muted, font=font(22))
    image.save(here / 'hero.png', optimize=True)
    image.resize((1200, 675), Image.Resampling.LANCZOS).save(here / 'social-card.png', optimize=True)
    image.crop((0, 52, 1672, 888)).resize((1280, 640), Image.Resampling.LANCZOS).save(here / 'social-preview.png', optimize=True)
    print('Wrote assets/hero.png, assets/social-card.png and assets/social-preview.png')


if __name__ == '__main__':
    main()
