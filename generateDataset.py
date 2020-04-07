import argparse
import re
from operator import itemgetter
from itertools import groupby
import fitz
from copy import copy

#define regexes
re_mash = re.compile(r"(\d+)°(?:C|F)\s(\d+)°(?:C|F)(\s(\d+mins)|)")
re_vol = re.compile(r"(\d+\.{0,1}\d*L)\s(\d+\.{0,1}\d*gal)\sVOLUME")
re_boilvol = re.compile(r"(\d+\.{0,1}\d*L)\s(\d+\.{0,1}\d*gal)\sBOIL\sVOLUME")
re_realabvog = re.compile(r"(\d+\.{0,1}\d*)%\s(\d+)\s(1[0-9]{3}|9[0-9]{2})")
re_number = re.compile(r"#([0-9]+)")
re_date = re.compile(r"FIRST BREWED\s(\w+\s\d+)")
re_desc = re.compile(r"(?:THIS BEER IS|)([\s\S]+)?BASICS") 

def generate(args):
    doc = fitz.open(args.file)  # any supported document type
    page = doc[int(args.page)]  # we want text from this page
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
    rl2 = page.searchFor("FOOD PAIRING")[0]  # rect list two
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
    pagerect.append(rl1 | rl2)  ### union rectangle 6
    rl2.y1 = 780
    pagerect.append(rl2)  ### rect 7

    for rect in pagerect:
        page.drawRect(rect, color=(1,0,0), width=2)
    
    page.getPixmap().writeImage("page-%i-test.png" % page.number)

    words = page.getTextWords()
    blocks = page.getTextBlocks()
    beer = {}
    for i,rect in enumerate(pagerect):
        mywords = [w for w in words if fitz.Rect(w[:4]) in rect]
        group = groupby(sorted(mywords,key=itemgetter(3, 0)), key=itemgetter(3))
        sentence_list = [" ".join(w[4] for w in gwords) for y1, gwords in group ]
        #print(sentence_list)
        bstr = "\n".join(sentence_list)
        # print(bstr)
        # print("-------------------------------------------")

        if i == 0: #header
            beer['id'] = re_number.search(bstr).group(1)
            t = sentence_list.index("#"+beer['id'])
            beer['name'] = sentence_list[t+1]
            beer['date'] = re_date.search(bstr).group(1)
            t = sentence_list.index("ABV IBU OG")
            beer['shortdesc'] = sentence_list[t+1]
            beer['real_abv'] = re_realabvog.search(bstr).group(1)
            beer['IBU'] = re_realabvog.search(bstr).group(2)
            beer['OG'] = re_realabvog.search(bstr).group(3)

        elif i == 1: #top left description
            if "THIS BEER IS" in sentence_list and "BASICS" in sentence_list:
                beer['description'] = " ".join(sentence_list[1:-1])

        elif i == 2: #basics
            beer['vol'] = re_vol.search(bstr).group(1)
            beer['boil_vol'] = re_boilvol.search(bstr).group(1)
            if "METHOD / TIMINGS" in sentence_list and "BASICS" in sentence_list:
                beer['abv'] = sentence_list[5][:-1]
                beer['FG'] = sentence_list[7]
                beer['EBC'] = sentence_list[11]
                beer['SRM'] = sentence_list[13]
                beer['pH'] = sentence_list[15]
                beer['attenuation'] = sentence_list[18]

        elif i == 3: #methods/timings
            t = sentence_list.index("MASH TEMP")
            mash = re_mash.search(sentence_list[t+1])
            beer['mash_temp'] = mash.group(1)
            if mash.group(4):
                beer['mash_time'] = mash.group(4)
            t = sentence_list.index('FERMENTATION')
            ferm = re_mash.search(sentence_list[t+1])
            beer['fermentation_temp'] = ferm.group(1)
            if "TWIST" in sentence_list:
                myblocks = [w for w in blocks if fitz.Rect(w[:4]) in rect]
                group = groupby(sorted(myblocks,key=itemgetter(3, 0)), key=itemgetter(3))
                sentence_list_1 = [" ".join(w[4] for w in gwords) for y1, gwords in group ]
                sentence_list = [re.sub(r"(\s+)",r" ",s) for s in sentence_list_1 ]
                t = sentence_list.index('TWIST')
                # print(sentence_list[t+1:])
                beer['twist'] = sentence_list[t+1:]

        elif i == 4: #ingredients is hard we change get text mode by block
            myblocks = [w for w in blocks if fitz.Rect(w[:4]) in rect]
            group = groupby(sorted(myblocks,key=itemgetter(3, 0)), key=itemgetter(3))
            sentence_list_1 = [" ".join(w[4] for w in gwords) for y1, gwords in group ]
            sentence_list = [re.sub(r"(\s+)",r" ",s) for s in sentence_list_1 ]
            # print(sentence_list)
            # bstr = "\n".join(sentence_list)
            if "HOPS" in sentence_list and "MALT" in sentence_list:
                t1 = sentence_list.index('MALT')
                t2 = sentence_list.index('HOPS')
                beer['malts'] = sentence_list[t1+1:t2]

            if "HOPS" in sentence_list and "YEAST" in sentence_list:
                t1 = sentence_list.index('HOPS')
                t2 = sentence_list.index('YEAST')
                beer['hops'] = sentence_list[t1+2:t2]

            if "YEAST" in sentence_list and "FOOD PAIRING" in sentence_list:
                t = sentence_list.index('YEAST')
                beer['yeast'] = " ".join( sentence_list[t+1:-1] ) #could be better

        elif i == 5: #food pairing
            t = sentence_list.index("FOOD PAIRING")
            pairinglist = list()
            for sent in sentence_list[t+1:]:
                if sent[0].isupper():
                    pairinglist.append(sent)
                elif len(pairinglist) == 0:
                    pairinglist.append(sent)
                else:
                    pairinglist[-1]+=sent
            beer['food_pairing'] = pairinglist  #could be better

        elif i == 6: #packaging
            if "KEG ONLY" in sentence_list:
                beer['keg_only'] = True
            else:
                beer['keg_only'] = False

        elif i == 7: # brewer's tip
            if "BREWER’S TIP" in sentence_list: 
                beer['brewers_tip'] = " ".join(sentence_list[1:])

    print(beer)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('-f', '--file', help='file to parse', required=True)
    parser.add_argument('-p', '--page')
    args = parser.parse_args()
    generate(args)
