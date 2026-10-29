#!/usr/bin/env python3
"""Render one finished TYVOR wordmark locally; never generate a glyph library.

Use an authorized Ethnocentric Regular copy with its matching desktop license.
The OTF remains external to the repository/firmware. See the asset provenance.
"""
import argparse
import hashlib
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

parser=argparse.ArgumentParser()
parser.add_argument('--font',required=True,type=Path)
parser.add_argument('--output',required=True,type=Path)
args=parser.parse_args()
expected='cda574639d6daf582ba221f5e820c18f53370ace4f12830376721ba8bb46d9b1'
assert hashlib.sha256(args.font.read_bytes()).hexdigest()==expected,'Use the verified official Ethnocentric Regular delivery'
size=(100,16);word='TYVOR'
for pixels in range(30,7,-1):
 font=ImageFont.truetype(str(args.font),pixels)
 box=font.getbbox(word)
 if box[2]-box[0]<=size[0]-4 and box[3]-box[1]<=size[1]-2:break
image=Image.new('L',size,0)
x=(size[0]-(box[2]-box[0]))//2-box[0]
y=(size[1]-(box[3]-box[1]))//2-box[1]
ImageDraw.Draw(image).text((x,y),word,font=font,fill=255)
image=image.point(lambda v:255 if v>=128 else 0).convert('1')
bounds=image.getbbox();assert bounds and 0<bounds[0]<bounds[2]<100 and 0<bounds[1]<bounds[3]<16
args.output.parent.mkdir(parents=True,exist_ok=True);image.save(args.output)
print(json.dumps({'font':font.getname(),'font_sha256':expected,'font_pixels':pixels,'canvas':size,'ink_bounds':bounds,'png_sha256':hashlib.sha256(args.output.read_bytes()).hexdigest()},indent=2))
