from multiprocessing import Array, Manager, Process, current_process, cpu_count
from pytz import timezone, utc
from typing import List

import csv
import datetime
import math
import os
import random
import sys
import time

'''
    TODO
    - panda with plot (jupyter notebook)
    - mathematical analysis
'''
successrate = None
destroyrate = None
mvpdiscount = None
rankdown = None
selecttable = None
table140 = None
table150 = None
table160 = None
table200 = None
level = None
msg = None
mvp = None
resmsg = None

# String concatenation without '+' for the performance issue
def concat_all(*strings: List[str]) -> str:
    str_list = []
    for st in strings:
        str_list.append(st)

    return ''.join(str_list)

# Get Time - KST(GMT+9)
def get_time() -> str:
    now = datetime.datetime.utcnow()
    kst = timezone('Asia/Seoul')
    return utc.localize(now).astimezone(kst).strftime('%Y%m%d_%H%M%S')

def simulation_logic(selecttable: List[int], start: int, goal: int, 
                     originalitemprice: int, j: int, sale: int, 
                     event1516: int, mvprank: int, pcroom: int) -> None:
    
    # Number of cases
    # event1516 x, sale x, pcsale o/x, prevention o/x
    # event1516 x, sale o, pcsale o/x, prevention o/x
    # event1516 o, sale x, pcsale o/x, prevention o/x
    
    # starcatch rate : *1.05

    finalsuccessrate = successrate[:]
    star = start
    currentmeso = 0
    currentdestroy = 0
    
    starcatch = 0
    prevention = 0

    # j == 0 :  no prevention,  no starcatch
    # j == 1 :  no prevention, yes starcatch
    # j == 2 : yes prevention,  no starcatch
    # j == 3 : yes prevention, yes starcatch
    if j & 1 == 1:
        starcatch = 1
    if j & 2 == 2:
        prevention = 1
        
    if event1516 == 1:
        for i in range (5, 20, 5):
            finalsuccessrate[i] = 100

    # get chance time if failcount == 2
    failcount = 0

    # starforce case : success, fail, destroy
    success = 0
    fail = 0
    destroy = 0

    # total number of attempts of 1 iteration
    trycount = 0

    while star < goal:
        # chance time or 15-16 event check
        if failcount == 2 or finalsuccessrate[star] == 100:
            success = 1
            fail = 0
            destroy = 0
        else :
            success = round(finalsuccessrate[star]*(1+starcatch*0.05)/100, 4)
            fail    = round((100-finalsuccessrate[star]*(1+starcatch*0.05))*(1-destroyrate[star]/100)/100, 4)
            destroy = round((100-finalsuccessrate[star]*(1+starcatch*0.05))*(destroyrate[star]/100)/100, 4)

        # weight normalization ( success + fail + destroy = 1 )
        normalization = success + fail + destroy
        success = round(success/normalization, 4)
        fail    = round(fail/normalization, 4)
        destroy = round(destroy/normalization, 4)

        result = random.choices(['success', 'fail', 'destroy'], weights=[success, fail, destroy])

        # sale formula 
        #   under 16 : cost*(1 - mvpdiscount - pcsale)*event
        #   over 16  : cost
        if star <= 16:
            currentmeso += selecttable[star]*(1-mvpdiscount[mvprank]-pcroom*0.05)*(1-sale*0.3)
        else:
            currentmeso += selecttable[star]

        # prevention cost
        if (star >= 12 and star <= 16) and prevention == 1 and failcount != 2 and finalsuccessrate[star] != 100:
            currentmeso += selecttable[star]

        # cases of result[0]

        # success
        if   result[0] == 'success':
            star += 1
            failcount = 0
        # fail or prevention
        elif rankdown[star] == 1 and (result[0] == 'fail' or 
                                     (result[0] == 'destroy' and prevention == 1 and (star >= 12 and star <= 16))):
            star -= 1
            failcount += 1
        # destroy
        elif result[0] == 'destroy' and (prevention != 1 or 
                                         star >= 17):
            star = 12
            currentdestroy += 1
            currentmeso += originalitemprice
            failcount = 0

        trycount += 1
    
    return [currentmeso, currentdestroy, trycount]

def multisimulation(samplelist: Manager,
                    maxmeso: Array, maxdestroy: Array, maxcount: Array, 
                    minmeso: Array, mindestroy: Array, mincount: Array, 
                    meanmeso: Array, meandestroy: Array, meancount: Array, 
                    iter_start: int, iter_end: int, start: int, goal: int, 
                    originalitemprice: int, sale: int, event1516: int, mvprank: int, pcroom: int) -> None:
    i = iter_start                                        
    print(f"Process PID({current_process().pid}) : Work (iteration number {iter_start} to {iter_end}) is allocated")
    while i < iter_end:
        for j in range(0,4):
            result = simulation_logic(selecttable, start, goal, originalitemprice, j, sale, event1516, mvprank, pcroom)

            # start force, target force, original item price, prevention on/off, starcatch on/off, 30% sale on/off, 1516event on/off, 
            # mvp rank(silver, gold, diamond, red, bronze), pc room sale on/off
            # ith iterations' total meso, destroy count, attempt count(try count)
            # be used to export to csv
            samplelist.append([start, goal, originalitemprice, j//2, j&1, sale, event1516, mvp[mvprank], pcroom, *result])

            meanmeso[j] += result[0]
            meandestroy[j] += result[1]
            meancount[j] += result[2]

            maxmeso[j] = max(maxmeso[j], result[0])
            maxdestroy[j] = max(maxdestroy[j], result[1])
            maxcount[j] = max(maxcount[j], result[2])

            minmeso[j] = min(minmeso[j], result[0])
            mindestroy[j] = min(mindestroy[j], result[1])
            mincount[j] = min(mincount[j], result[2])

        i += 1

    print(f"Process PID({current_process().pid}) : work done, iteration count : {i-iter_start}")

def simulation() -> None:
    global selecttable
    selecttable = []

    iteration = 0
    goal = 0

    # SynchronizedArray
    minmeso =     Array('d', [float("inf"), float("inf"), float("inf"), float("inf")])
    mindestroy =  Array('d', [float("inf"), float("inf"), float("inf"), float("inf")])
    mincount =    Array('d', [float("inf"), float("inf"), float("inf"), float("inf")])

    maxmeso =     Array('d', [0, 0, 0, 0])
    maxdestroy =  Array('d', [0, 0, 0, 0])
    maxcount =    Array('d', [0, 0, 0, 0])

    meanmeso =    Array('d', [0, 0, 0, 0])
    meandestroy = Array('d', [0, 0, 0, 0])
    meancount =   Array('d', [0, 0, 0, 0])
    # SynchronizedArray
    
    sale = 0
    event1516 = 0
    mvprank = 0
    pcroom = 0
    
    originalitemprice = 0

    with Manager() as manager:
        # multiprocessing list, Save all samples' information
        samplelist = manager.list()

        # process array
        processes = []

        print(  "\nSelect item information you want to check\n"
                "---------------------------\n"
                "1 : 140, 2 : 150, 3 : 160, 4 : 200")
        
        try:
            select = int(input())

            if select >= 1 and select <= 4:
                if select == 1:
                    selecttable = table140[:]
                elif select == 2:
                    selecttable = table150[:]
                elif select == 3:
                    selecttable = table160[:]
                else:
                    selecttable = table200[:]
        
        
            # total attempt size : iteration * 4
            print("\nType sample size( > 4 )")
            iteration = int(input())
            
            # start starforce (17, 18 or 22 are usually used)
            print("\nType start force( 0 ~ 24 )")
            start = int(input())

            # target starforce (17, 18 or 22 are usually used)
            print("\nType target force( 1 ~ 25, must be larger than start )")
            goal = int(input())

            print("\nType Original Item price( Positive Integer )")
            originalitemprice = int(input())

            print("\nEnable 30 percent discount?\n"
                  "---------------------------\n"
                  "0 : no, otherwise : yes")
            sale = int(input())
            if sale < 0 or sale >= 1:
                sale = 1
            if sale == 0:
                print("\nEnable 1516 event\n"
                      "---------------------------\n"
                      "0 : no, otherwise : yes")
                event1516 = int(input())
                if event1516 < 0 or event1516 >= 1:
                    event1516 = 1

            print("\nselect mvprank(0 : silver, 1 : gold, 2 : diamond, 3 : red, otherwise : bronze)\n"
                  "and pcroom(0 : no, otherwise : yes)\n"
                  "-----------------------------------------\n"
                  "ex1) 3 0 : Enable MVP RED Sale   , Disable PC Room sale\n"
                  "ex2) 4 1 : Enable MVP Bronze Sale,  Enable PC Room sale")
                                            
            mvprank, pcroom = map(int, input().split())
            if mvprank < 0 or mvprank >= 4:
                mvprank = 4
            if pcroom  < 0 or pcroom  >= 1:
                pcroom  = 1

            nump = cpu_count()
            iter_start = 0
            iter_end = round(iteration/nump)

            if start >= goal:
                print(f"\ncannot simulate. Goal must be larger than start. {start} -> {goal}")

            else:
                print("\nPlease Wait...\n")
                for i in range(0,nump):
                    p = Process(target=multisimulation, args=(samplelist,
                                                            maxmeso, maxdestroy, maxcount, 
                                                            minmeso, mindestroy, mincount, 
                                                            meanmeso, meandestroy, meancount, 
                                                            iter_start, iter_end, start, goal, originalitemprice, sale, event1516, mvprank, pcroom))
                    p.start()
                    processes.append(p)
                    iter_start = iter_end
                    iter_end = round((i+2)*iteration/nump)

                for p in processes:
                    p.join()
                    p.close()

                for j in range(0,4):
                    meanmeso[j]    = round(meanmeso[j]/iteration,   -2)
                    meandestroy[j] = round(meandestroy[j]/iteration, 2)
                    meancount[j]   = round(meancount[j]/iteration,   2)

                resultmsg = concat_all(f"\nResult\n--------------------------------------------------------------------\n",
                                       f"Item Level : {level[select-1]}\nSample size : {iteration} * 4 = {iteration*4}\n",
                                       f"Start Starforce : {start}, End Starforce : {goal}\nOriginal item price : {originalitemprice}\n",
                                       f"Enable Saleevent : {msg[sale]}\nEnable event1516 : {msg[event1516]}\nMVP Rank : {mvp[mvprank]}\nPC room : {msg[pcroom]}\n",
                                       f"--------------------------------------------------------------------\n")
                for i in range(0, 4):
                    resultmsg = concat_all(resultmsg,
                                           f"\n--------------------------------------------------------------------\n",
                                           f"Case {i+1}. {resmsg[i]}\n",
                                           f"Max meso : {maxmeso[i]:.0f}, Avg meso : {meanmeso[i]:.0f}, Min meso : {minmeso[i]:.0f}\n",
                                           f"Max destroy : {maxdestroy[i]:.0f}, Avg destroy : {meandestroy[i]:.0f}, Min destroy : {mindestroy[i]:.0f}\n",
                                           f"Max attempts : {maxcount[i]:.0f}, Avg attempts : {meancount[i]:.0f}, Min attempts : {mincount[i]:.0f}\n",
                                           f"--------------------------------------------------------------------\n")
                                        
                print(resultmsg)

                nowtime = get_time()

                print("Export all samples' data to csv and result to txt?\n"
                    "---------------------------\n"
                    "0 : no, otherwise : yes")

                save = int(input())
                if save != 0:
                    csvname = concat_all(nowtime,".csv")
                    txtname = concat_all(nowtime,".txt")
                    with open(csvname, "w", newline="") as savefile:
        
                        csvwriter = csv.writer(savefile)
                        csvindex = 1

                        # Data Format
                        # In case of boolean, 0 : Disable, 1 : Enable
                        fields = ['', 
                                  'start', 'Target', 'Original Item Price', 'Prevention', 'Starcatch',
                                  'Event 30per sale', 'Event 1516', 'MVP Rank', 'PC room sale',
                                  'Total spend meso', 'Total destroy count', 'Total try count']
                        csvwriter.writerow(fields)

                        for row in samplelist:
                            csvwriter.writerow([csvindex, *row])
                            csvindex += 1

                        print(f"\nExporting to csv is completed.\n"
                              f"------------------------------------\n"
                              f"Filename : {csvname}\nTotal number of samples: {csvindex-1}\nFilesize : {savefile.seek(0, os.SEEK_END)} bytes\n")

                        savefile.close()
                    
                    with open(txtname, "w", newline="") as savefile:
                        savefile.write(resultmsg)

                        print(f"\nExporting to txt is completed.\n"
                              f"------------------------------------\n"
                              f"Filename : {txtname}\nFilesize : {savefile.seek(0, os.SEEK_END)} bytes\n")

                        savefile.close()

                print("Wait 10 seconds...\n")
                time.sleep(10)            

        except Exception as e:
            print(f"\nException Alerted. {e}\n")

def cost_check():
    looktable = []

    print(  "\nSelect item information you want to check\n"
            "---------------------------\n"
            "1 : 140, 2 : 150, 3 : 160, 4 : 200")

    while True:
        try:
            minsum = 0
            select = int(input())
            
            if select >= 1 and select <= 3:
                if select == 1:
                    looktable = table140[:]
                elif select == 2:
                    looktable = table150[:]
                elif select == 3:
                    looktable = table160[:]
                else:
                    looktable = table200[:]
                
                print("\n--------------------------------------------------------------------")
                for i in range(0, 25):
                    print(f"{i} to {i+1} : meso : {looktable[i]:.0f}, successrate : {successrate[i]},"
                          f"failrate : {round((100-successrate[i])*(1-destroyrate[i]/100), 1)}, destroyrate : {(100-successrate[i])*destroyrate[i]/100}")

                for i in range(0, 21):
                    minsum += looktable[i]
                
                print(f"minimum cost 0 to 22 : {minsum}")
                print("--------------------------------------------------------------------\n")
        
        except Exception as e:
            print(f"\nException Alerted. {e}\n")
            break

def exit_func():
    sys.exit("Program Terminated Successfully")

def home():
    funcs = { '1' : simulation,
              '2' : cost_check,
              '3' : exit_func }

    while True:
        try:
            print("Select Menu\n"
                  "---------------------------\n"
                  "1. simulation\n"
                  "2. cost check\n"
                  "3. exit")
            select = int(input())
            func = funcs[str(select)]

        except Exception as e:
            print(f"\nException Alerted. {e}\n")
            func = funcs['3']
            
        finally:
            func()


def main():
    global table140
    global table150
    global table160
    global table200

    table140 = []
    table150 = []
    table160 = []
    table200 = []

    global successrate
    global destroyrate
    global rankdown
    global mvpdiscount
    successrate = [ 95, 90, 85, 80, 75, 
                    70, 65, 60, 55, 50, 
                    50, 45, 40, 35, 30,
                    30, 30, 30, 30, 30,
                    30, 30,  3,  2,  1 ]
    destroyrate = [ 0, 0, 0, 0, 0,
                    0, 0, 0, 0, 0,
                    0, 0, 1, 2, 2,
                    3, 3, 3, 4, 4,
                    10, 10, 20, 30, 40]
    rankdown = [0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 1, 1, 1, 1,
                0, 1, 1, 1, 1,
                0, 1, 1, 1, 1 ]
    mvpdiscount = [0.03, 0.05, 0.1, 0.1, 0]

    global level
    global msg
    global mvp
    global resmsg
    level = ['140', '150', '160', '200']
    msg = ['no', 'yes']
    mvp = ['Silver', 'Gold', 'Diamond', 'Red', 'Bronze']
    resmsg = ['prevention : off, starcatch : off',
              'prevention : off, starcatch : on' ,
              'prevention : on, starcatch : off' ,
              'prevention : on, starcatch : on'   ]
    
    for i in range(0, 25):
        a = 140
        b = 150
        c = 160
        d = 200
        if i >= 0 and i <= 9:
            table140.append(round(1000+math.pow(a,3)*(i+1)/25, -2))
            table150.append(round(1000+math.pow(b,3)*(i+1)/25, -2))
            table160.append(round(1000+math.pow(c,3)*(i+1)/25, -2))
            table200.append(round(1000+math.pow(d,3)*(i+1)/25, -2))
        elif i >= 10 and i <= 14:
            table140.append(round(1000+math.pow(a,3)*math.pow((i+1), 2.7)/400, -2))
            table150.append(round(1000+math.pow(b,3)*math.pow((i+1), 2.7)/400, -2))
            table160.append(round(1000+math.pow(c,3)*math.pow((i+1), 2.7)/400, -2))
            table200.append(round(1000+math.pow(d,3)*math.pow((i+1), 2.7)/400, -2))
        else:
            table140.append(round(1000+math.pow(a,3)*math.pow((i+1), 2.7)/400, -2))
            table150.append(round(1000+math.pow(b,3)*math.pow((i+1), 2.7)/200, -2))
            table160.append(round(1000+math.pow(c,3)*math.pow((i+1), 2.7)/200, -2))
            table200.append(round(1000+math.pow(d,3)*math.pow((i+1), 2.7)/200, -2))

    home()

if __name__ == '__main__':
    main()