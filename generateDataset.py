import argparse
import re
from operator import itemgetter
from itertools import groupby
import json
import os
import fitz

#define regexes
re_mash = re.compile(r"(\d+\.?\d*) ?°(?:C|F)\s(\d+\.?\d*) ?°(?:C|F)(\s(\d+mins)|)")
re_vol = re.compile(r"(?<!BOIL\s)VOLUME\s(\d+\.{0,1}\d*L)\s(\d+\.{0,1}\d*(gal|))")
re_boilvol = re.compile(r"BOIL\sVOLUME\s(\d+\.{0,1}\d*L)\s(\d+\.{0,1}\d*(gal|))")
re_realabvog = re.compile(r"(\d+\.?\d*%?) +(\d+.?)\s([0-9]*\.?[0-9]*)")
re_number = re.compile(r"#([0-9]+)")
re_date = re.compile(r"FIRST BREWED\s(\w*\s*\d+)")
re_malt = re.compile(r"([\w\W]+?)\s+(\d+\.?\d*)k?g?\s+(\d+\.?\d*)lb")
re_hops = re.compile(r"([\w\s]*?)\s(\d+\.?\d*)g?\s([\w\s]*?)\s(Bitteri?n?g?|Flavour|Aroma)")

def generate(args,page):
    pagerect = list()
    # rl1 = page.searchFor("#")[0]
    rl1 = fitz.Rect(100,30,130,70)  # sometimes in text so hardcode
    # rl2 = page.searchFor("THIS BEER IS")[0]  # sometimes in text so hardcode
    rl2 = fitz.Rect(20,182,555,197)  # sometimes in text so hardcode
    if (page.number%2):
        rl2.x1 = 575
        rl2.x0 = 40
    pagerect.append(rl1 | rl2)  ### union rectangle 0 (header)
    rectdesc = fitz.Rect(10,120,410,160) 
    if (page.number%2):
        rectdesc.x1 += 20
    # rl1 = page.searchFor("THIS BEER IS")[0]
    rl1 = fitz.Rect(40,182,180,197)  # sometimes in text so hardcode
    rl2 = page.searchFor("BASICS")[0]
    rl3 = page.searchFor("METHOD / TIMINGS")[0]  # sometimes food and method reversed
    method2 = 0
    if (rl3.x0 > 150): #method is in 2nd row
        rl3 = page.searchFor("FOOD PAIRING")[0]
        method2 = 1
    rl2.x1 = 180
    rl3.x1 = 180
    if (page.number%2):
        rl2.x1 = 200
        rl3.x1 = 200
    pagerect.extend((rl1 | rl2, rl2 | rl3))  ### union rectangle 1 and 2
    rl3.y1 = 780
    pagerect.append(rl3) ### rect 3
    
    rl1 = page.searchFor("INGREDIENTS")[0]
    if rl1.y0 > 190:
        rl1 = page.searchFor("INGREDIENTS")[1]
    rl2 = page.searchFor("FOOD PAIRING")
    if method2:
        rl2 = page.searchFor("METHOD / TIMINGS")  # sometimes food and method reversed
    if rl2 == []:
        rl2 = (rl1,) 
        rl2[0].y1 = 780
    rl2 = rl2[0]
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
    if method2:
        pagerect[3],pagerect[5] = pagerect[5],pagerect[3]
    
    rl1 = page.searchFor("PACKAGING")[0]
    rl2 = page.searchFor("BREWER’S TIP")[0]
    rl2.x1 = 555
    if (page.number%2):
        rl2.x1 = 575
    rlt = rl1 | rl2
    rlt.y0 += 20 # to crop for photo
    rlt.y1 -= 35
    rlt.x1 -= 5
    pagerect.append(rlt)  ### union rectangle 6
    if special:
        rlr = page.searchFor("FOOD PAIRING")[0]
        pagerect.append(rlr | rl2)  ### union rectangle 7 special
    else:
        rl2.y1 = 780
        pagerect.append(rl2)  ### rect 7

    # FOR TESTING RECTANGLES :
    if args.debug:
        for rect in pagerect:
            page.drawRect(rect, color=(1,0,0), width=2) 
        page.drawRect(rectdesc, color=(0,1,0), width=2) 
        page.getPixmap().writeImage("page-%i-test.png" % page.number)

    words = page.getTextWords()
    blocks = page.getTextBlocks()
    beer = {}
    for i,rect in enumerate(pagerect):
        myblocks = [w for w in blocks if fitz.Rect(w[:4]).intersect(rect)]
        # myblocks = [w for w in blocks if fitz.Rect(w[:4]) in rect]
        groupblock = groupby(sorted(myblocks,key=itemgetter(3, 0)), key=itemgetter(3))
        sentence_list_1 = [" ".join(w[4] for w in gwords) for y1, gwords in groupblock ]
        sentence_list_blk = [re.sub(r"(\s+)",r" ",s) for s in sentence_list_1 ]
        blkstr = "\n".join(sentence_list_blk)
        blkstr2 = "\n".join(sentence_list_1)
        sentence_list_blk_2 = blkstr2.split("\n")
        
        if args.debug:
            # print(i,sentence_list_blk)
            print(i,sentence_list_blk)
            print(blkstr2)

        try:
            if i == 0: #header
                descblock = [w for w in words if fitz.Rect(w[:4]) in rectdesc]
                descgroupblock = groupby(sorted(descblock,key=itemgetter(3, 0)), key=itemgetter(3))
                descsentence_list_1 = [" ".join(w[4] for w in gwords) for y1, gwords in descgroupblock ]
                
                beer['id'] = re_number.search(blkstr2).group(1)
                t = sentence_list_blk_2.index("#"+beer['id'])
                beer['name'] = sentence_list_blk_2[t+1]
                
                if descsentence_list_1 != []:
                    beer['shortdesc'] = descsentence_list_1[0]
                else:
                    print(f"HEADER order problem trying to correct: {page.number} id:{beer['id']} ")
                    print(f"leaving empty")
                    # beer['shortdesc'] = sentence_list_blk_2[t+2]

                if s:=re_date.search(blkstr2):
                    beer['date'] = s.group(1)
                else:
                    print(f"No date data: {page.number} id:{beer['id']} ")

                abvibuog = re_realabvog.search(blkstr2)
                if abvibuog:
                    beer['real_abv'] = abvibuog.group(1)
                    beer['IBU'] = abvibuog.group(2)
                    beer['OG'] = abvibuog.group(3)
                # elif "ABV" in sentence_list_blk_2[t+3]:
                    # beer['real_abv'] = re.search(r"\d+\.{0,1}\d*%",sentence_list_blk_2[t+4]).group()
                elif "ABV" in blkstr2:
                    beer['real_abv'] = re.search(r"\d+\.{0,1}\d*%",blkstr2).group()

            elif i == 1: #top left description
                if "THIS BEER IS" in sentence_list_blk_2 and "BASICS" in sentence_list_blk_2:
                    t1 = sentence_list_blk_2.index("THIS BEER IS")
                    t2 = sentence_list_blk_2.index("BASICS")
                    beer['description'] = " ".join(sentence_list_blk_2[t1+1:t2])
                else:
                    print(f"No description data: {page.number} id:{beer['id']} ")

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
                else:
                    print(f"No mashing data: {page.number} id:{beer['id']} ")
                try:
                    t = sentence_list_blk.index('FERMENTATION')
                except:
                    #check if ferment is substring
                    for j,it in enumerate(sentence_list_blk):
                        if "FERMENTATION" in it:
                            t = j
                            break
                    else:
                        raise
                ferm = re_mash.search(sentence_list_blk[t+1])
                if ferm:    
                    beer['fermentation_temp'] = ferm.group(1)
                else:
                    print(f"No fermentation data: {page.number} id:{beer['id']}")
                if "TWIST" in sentence_list_blk:
                    t = sentence_list_blk.index('TWIST')
                    beer['twist'] = sentence_list_blk[t+1:]
                elif "TWIST/ BREWHOUSE ADDITIONS" in sentence_list_blk:
                    t = sentence_list_blk.index('TWIST/ BREWHOUSE ADDITIONS')
                    beer['twist'] = sentence_list_blk[t+1:]


            elif i == 4: #ingredients is hard we change get text mode by block
                if "HOPS" in sentence_list_blk and "MALT" in sentence_list_blk:
                    t1 = sentence_list_blk.index('MALT')
                    t2 = sentence_list_blk.index('HOPS')
                    # beer['malts'] = [x.split() for x in sentence_list_blk[t1+1:t2]]
                    beer['malts'] = re_malt.findall( " ".join(sentence_list_blk[t1+1:t2]) )
                else:
                    print(f"No malts data: {page.number} id:{beer['id']} ")

                if "HOPS" in sentence_list_blk and "YEAST" in sentence_list_blk:
                    t1 = sentence_list_blk.index('HOPS')
                    t2 = sentence_list_blk.index('YEAST')
                    # beer['hops'] = [x.split() for x in sentence_list_blk[t1+2:t2]]
                    beer['hops'] = re_hops.findall( " ".join(sentence_list_blk[t1+2:t2]) )
                else:
                    print(f"No hops data: {page.number} id:{beer['id']} ")

                if "YEAST" in sentence_list_blk and "FOOD PAIRING" in sentence_list_blk:
                    t = sentence_list_blk.index('YEAST')
                    beer['yeast'] = sentence_list_blk[t+1:-1]#could be better
                elif "YEAST" in sentence_list_blk:
                    t = sentence_list_blk.index('YEAST')
                    beer['yeast'] = [s for s in sentence_list_blk[t+1:] if "FOOD PAIRING" not in s] #could be better
                else:
                    print(f"No yeast data: {page.number} id:{beer['id']} ")


            elif i == 5: #food pairing
                try:
                    t = sentence_list_blk.index("FOOD PAIRING")
                    beer['food_pairing'] = sentence_list_blk[t+1:]
                except:
                    if "FOOD PAIRING" in sentence_list_blk[0]:
                        beer['food_pairing'] = sentence_list_blk[1:]
                    else:
                        print(f"No Food Pairing: {page.number} id:{beer['id']}")
                        # print(sentence_list_blk)

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
            print(e)
            print(page.number)
            print(sentence_list_blk)
            print('--------------------')
            print(sentence_list_1)
            print('--------------------')
            print(blkstr)
            print('--------------------')
            print(blkstr2)
            print(beer)
            # raise


    # print(beer)
    page.getPixmap(clip=pagerect[6]).writeImage(os.path.join(args.output,f"{beer['id']}.png"))
    return beer


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('-f', '--file', help='file to parse', required=True)
    parser.add_argument('-p', '--page')
    parser.add_argument('-o', '--output', required=True)
    parser.add_argument('-d', '--debug', action='store_true')
    args = parser.parse_args()
    doc = fitz.open(args.file)  # any supported document type

    if args.page:
        print(f"Extracting page {args.page}")
        page = doc[int(args.page)]  # we want text from this page
        beer = generate(args,page)
        print(beer)
    else:
        print("Extracting whole book")
        beers = []
        for page in range(21,425):
            print(f"Extract page: {page}")
            page = doc[int(page)]  # we want text from this page
            beers.append(generate(args,page))
        # print(beers)
        with open('result.json', 'w') as fp:
            json.dump(beers,fp)
