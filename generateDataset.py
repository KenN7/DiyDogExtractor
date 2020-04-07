import argparse
import re
from operator import itemgetter
from itertools import groupby
import os
import fitz

#define regexes
re_mash = re.compile(r"(\d+)°(?:C|F)\s(\d+)°(?:C|F)(\s(\d+mins)|)")
re_vol = re.compile(r"(?<!BOIL\s)VOLUME\s(\d+\.{0,1}\d*L)\s(\d+\.{0,1}\d*(gal|))")
re_boilvol = re.compile(r"BOIL\sVOLUME\s(\d+\.{0,1}\d*L)\s(\d+\.{0,1}\d*(gal|))")
re_realabvog = re.compile(r"OG (\d+\.{0,1}\d*)%{0,1}\s(.+?)\s([0-9]*\.{0,1}[0-9]*)")
re_number = re.compile(r"#([0-9]+)")
re_date = re.compile(r"FIRST BREWED\s(\w*\s*\d+)")
re_desc = re.compile(r"(?:THIS BEER IS|)([\s\S]+)?BASICS") 

def generate(args,folder):
    pagerect = list()
    rl1 = page.searchFor("#")[0]  # rect list one
    # rl2 = page.searchFor("THIS BEER IS")[0]  # sometimes in text so hardcode
    rl2 = fitz.Rect(20,182,555,197)  # sometimes in text so hardcode
    if (page.number%2):
        rl2.x1 = 575
        rl2.x0 = 40
    pagerect.append(rl1| rl2)  ### union rectangle 0
    
    # rl1 = page.searchFor("THIS BEER IS")[0]
    rl1 = fitz.Rect(40,182,180,197)  # sometimes in text so hardcode
    rl2 = page.searchFor("BASICS")[0]  # rect list two3
    rl3 = page.searchFor("METHOD / TIMINGS")[0]  # rect list two
    rl2.x1 = 180
    rl3.x1 = 180
    if (page.number%2):
        rl2.x1 = 200
        rl3.x1 = 200
    pagerect.extend((rl1 | rl2, rl2 | rl3))  ### union rectangle 1
    rl3.y1 = 780
    pagerect.append(rl3) ### rect 3
    
    rl1 = page.searchFor("INGREDIENTS")[0]  # rect list one
    rl2 = page.searchFor("FOOD PAIRING")  # rect list two
    if rl2 == []:
        rl2 = (rl1,) 
    rl2 = rl2[0]  # rect list two
    if rl2.x0 > 300: #food pairing is sometimes on third column
        special = 1
        rl1.y1 = 780
        rl1.x1 = 340
        if (page.number%2):
            rl1.x1 = 360
        pagerect.append(rl1) # rect4 if pairing next 
        rl2.x1 = 555
        if (page.number%2):
            rl2.x1 = 575
        rl2.y1 = 780
        pagerect.append(rl2) # rect5 if pairing next 
    else:
        special = 0
        rl2.x1 = 340
        if (page.number%2):
            rl2.x1 = 360
        pagerect.append(rl1 | rl2)  ### union rectangle 4
        rl2.y1 = 780
        pagerect.append(rl2) ### rect 5
    
    rl1 = page.searchFor("PACKAGING")[0]  # rect list one
    rl2 = page.searchFor("BREWER’S TIP")[0]  # rect list two
    rl2.x1 = 555
    if (page.number%2):
        rl2.x1 = 575
    rlt = rl1 | rl2
    rlt.y0 += 20 # to crop for photo
    rlt.y1 -= 35
    pagerect.append(rlt)  ### union rectangle 6
    if special:
        rlr = page.searchFor("FOOD PAIRING")[0]
        pagerect.append(rlr | rl2)  ### union rectangle 7 special
    else:
        rl2.y1 = 780
        pagerect.append(rl2)  ### rect 7

    # FOR TESTING RECTANGLES :
    # for rect in pagerect:
    #     page.drawRect(rect, color=(1,0,0), width=2) 
    # page.getPixmap().writeImage("page-%i-test.png" % page.number)

    words = page.getTextWords()
    blocks = page.getTextBlocks()
    beer = {}
    for i,rect in enumerate(pagerect):
        myblocks = [w for w in blocks if fitz.Rect(w[:4]).intersect(rect)]
        groupblock = groupby(sorted(myblocks,key=itemgetter(3, 0)), key=itemgetter(3))
        sentence_list_1 = [" ".join(w[4] for w in gwords) for y1, gwords in groupblock ]
        sentence_list_blk = [re.sub(r"(\s+)",r" ",s) for s in sentence_list_1 ]
        blkstr = "\n".join(sentence_list_blk)
        # print("-------------------------------------------")
        try:
            if i == 0: #header
                beer['id'] = re_number.search(blkstr).group(1)
                t = sentence_list_blk.index("#"+beer['id'])
                beer['name'] = sentence_list_blk[t+1]
                beer['shortdesc'] = sentence_list_blk[t+2]
                beer['date'] = re_date.search(blkstr).group(1)
                abvibuog = re_realabvog.search(blkstr)
                if abvibuog:
                    beer['real_abv'] = abvibuog.group(1)
                    beer['IBU'] = abvibuog.group(2)
                    beer['OG'] = abvibuog.group(3)
                elif "ABV" in sentence_list_blk[t+3]:
                    beer['real_abv'] = re.search(r"\d+\.{0,1}\d*%",sentence_list_blk[t+3]).group()

            elif i == 1: #top left description
                if "THIS BEER IS" in sentence_list_blk and "BASICS" in sentence_list_blk:
                    beer['description'] = " ".join(sentence_list_blk[1:-1])

            elif i == 2: #basics
                if s:=re_vol.search(blkstr):
                    beer['vol'] = s.group(1)
                if s:=re_boilvol.search(blkstr):
                    beer['boil_vol'] = s.group(1)
                if s:=re.search(r"ABV (\d+\.{0,1}\d*(%|))",blkstr):
                    beer['abv'] = s.group(1)
                if s:=re.search(r"FG (\d+\.{0,1}\d*)",blkstr):
                    beer['FG'] = s.group(1)
                if s:=re.search(r"EBC (\d+\.{0,1}\d*)",blkstr):
                    beer['EBC'] = s.group(1)
                if s:=re.search(r"SRM (\d+\.{0,1}\d*)",blkstr):
                    beer['SRM'] = s.group(1)
                if s:=re.search(r"PH (\d+\.{0,1}\d*)",blkstr):
                    beer['pH'] = s.group(1)
                if s:=re.search(r"LEVEL (\d+\.{0,1}\d*(%|))",blkstr):
                    beer['attenuation'] = s.group(1)

            elif i == 3: #methods/timings
                t = sentence_list_blk.index("MASH TEMP")
                mash = re_mash.search(sentence_list_blk[t+1])
                if mash:    
                    beer['mash_temp'] = mash.group(1)
                if mash.group(4):
                    beer['mash_time'] = mash.group(4)
                t = sentence_list_blk.index('FERMENTATION')
                ferm = re_mash.search(sentence_list_blk[t+1])
                if ferm:    
                    beer['fermentation_temp'] = ferm.group(1)
                if "TWIST" in sentence_list_blk:
                    t = sentence_list_blk.index('TWIST')
                    beer['twist'] = sentence_list_blk[t+1:]

            elif i == 4: #ingredients is hard we change get text mode by block
                if "HOPS" in sentence_list_blk and "MALT" in sentence_list_blk:
                    t1 = sentence_list_blk.index('MALT')
                    t2 = sentence_list_blk.index('HOPS')
                    beer['malts'] = sentence_list_blk[t1+1:t2]

                if "HOPS" in sentence_list_blk and "YEAST" in sentence_list_blk:
                    t1 = sentence_list_blk.index('HOPS')
                    t2 = sentence_list_blk.index('YEAST')
                    beer['hops'] = sentence_list_blk[t1+2:t2]

                if "YEAST" in sentence_list_blk and "FOOD PAIRING" in sentence_list_blk:
                    t = sentence_list_blk.index('YEAST')
                    beer['yeast'] = " ".join( sentence_list_blk[t+1:-1] ) #could be better

            elif i == 5: #food pairing
                try:
                    t = sentence_list_blk.index("FOOD PAIRING")
                    beer['food_pairing'] = sentence_list_blk[t+1:]
                except:
                    print(f"No Food Pairing: {page.number}")
                    print(sentence_list_blk)

            elif i == 6: #packaging
                if "KEG ONLY" in sentence_list_blk:
                    beer['keg_only'] = True
                else:
                    beer['keg_only'] = False

            elif i == 7: # brewer's tip
                if "BREWER’S TIP" in sentence_list_blk and "FOOD PAIRING" in sentence_list_blk: 
                    beer['brewers_tip'] = " ".join(sentence_list_blk[1:-1])
                else:
                    beer['brewers_tip'] = " ".join(sentence_list_blk[1:])

        except Exception as e:
            # print(bstr)
            print(e)
            print(page.number)
            print(sentence_list_blk)
            # raise


    # print(beer)
    page.getPixmap(clip=pagerect[6]).writeImage(os.path.join(folder,f"{beer['id']}.png"))
    return beer


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('-f', '--file', help='file to parse', required=True)
    parser.add_argument('-p', '--page')
    parser.add_argument('-o', '--output', required=True)
    args = parser.parse_args()
    
    folder = args.output
    doc = fitz.open(args.file)  # any supported document type

    if args.page:
        print(f"Extracting page {args.page}")
        page = doc[int(args.page)]  # we want text from this page
        beer = generate(page,folder)
        print(beer)
    else:
        print("Extracting whole book")
        beers = []
        for page in range(21,425):
            print(f"Extract page: {page}")
            page = doc[int(page)]  # we want text from this page
            beers.append(generate(page,folder))
        print(beers)
