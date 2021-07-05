'''
Cosc 364 assignment 1 rip router
By Jacob Early and Jethro Jones Long
'''

import struct
import socket
import select
import random
import sys
import time
# setup fuctions =====================================================================================


def readconfigfile(configfilename):
    '''Takes a config file name and returns router id, input ports and outputs from it
    Router id: is an int between 1 and 64000
    input ports: is a list of ports between 1024 and 64000 with no duplicates to listen on
    outputs: is a list of [outputport, metric, outputid] for each output from this router'''

    configlist = []
    configfile = open(configfilename, 'r')
    for line in configfile.readlines():
        line = line.split(', ')
        configlist.append(line)

    # positive int between 1 and 64000
    routerid = int(configlist[0][1])
    if routerid < 1 or routerid > 64000:
        print('router id out of range')
        exit()

    # 1024 <= port <= 64000 no duplicates
    inputports = []
    for inputport in configlist[1][1:]:
        if int(inputport) in inputports or int(inputport) < 1024 or int(inputport) > 6400:
            print('input ports error')
            exit()
        else:
            inputports.append(int(inputport))

    # port number - metric - router id 1024 <= port <= 64000 no duplicates with input and metric conforming to rip protocol
    outputs = []
    outputports = []
    outputids = []
    for output in configlist[2][1:]:
        output = output.split('-')
        outputport = int(output[0])
        metric = int(output[1])
        outputid = int(output[2])

        if int(outputport) in inputports or int(outputport) in outputports or int(outputport) < 1024 or int(outputport) > 6400:
            print('output port error')
            exit()

        if outputid in outputids or outputid == routerid or outputid < 1 or outputid > 64000:
            print('outputid error')
            exit()

        # metric of a network is an integer between 1 and 15 inclusive from rip spec
        if metric < 1 or metric > 15:
            print('metric error')
            exit()

        outputs.append([outputport, metric, outputid])
        outputports.append(outputport)

    return(routerid, inputports, outputs)


def createroutingtable(outputs):
    '''takes a list of outputs from reading the config file and creates a routing table for this router
    the routing table is a dictionary of router ids : [firsthop, metric, flag, timers]'''
    table = {}
    flag = 0
    timers = [0, 0]

    for output in outputs:
        routerid = output[2]
        firsthop = routerid
        metric = output[1]
        table[routerid] = [firsthop, metric, flag, timers]

    return(table)


def outputportdict(outputs):
    '''creates a dictionary of output ports : router ids'''
    outputports = {}
    for output in outputs:
        outputports[output[0]] = output[2]

    return(outputports)

# Socket fuctions ===========================================================================================


def create_message(table, routerid, outputs, port, triggered=0):
    ''' Creates a response message with correct header and body in bytes
    '''
    headerformat = '!BBH'
    ripentryformat = '!HHIIII'
    command = 2  # Command response message
    version = 2  # rip version
    header = struct.pack(headerformat, command, version, routerid)

    for routerid in table:
        value = table[routerid]
        metric = value[1]
        afi = 0
        if triggered == 1 and value[2] == 0:
            continue  # Skips if part of a triggered update and not flagged
        if outputs[port] == routerid:
            metric = 16  # poision reverse
        ripentry = struct.pack(ripentryformat, afi, 0, routerid, 0, 0, metric)
        header += ripentry

    return(header)


def listen(inputports):
    ''' listens on all input sockets for data and returns the data packets
    '''
    data = 0
    socketlist = []
    for i in range(0, len(inputports)):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(('', int(inputports[i])))
        socketlist.append(sock)

    sockets, b ,c = select.select(socketlist, [], [], 2)
    if sockets != []:
        s = sockets[0]
        s.settimeout(10)
        data, addr = s.recvfrom(1024)

    return(data)


def send_message(table, routerid, outputs, triggered=0):
    '''Sends update message'''
    udp_ip = "127.0.0.1"
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    for port in outputs:
        update = create_message(table, routerid, outputs, port, triggered)
        server_socket.sendto(update, (udp_ip, port))
    printtable(table, routerid)
    if triggered == 1:
        for key in table:
            table[key][2] = 0

    delay = random.randint(1, 5)
    return(delay)

# processing data ======================================================================


def processmsg(data):
    '''Takes a received rip packet and unpacks the bytes into a more usable table
    returns a list in the form[header, [router id, metric]]'''
    headerformat = '!BBH'
    ripentryformat = '!HHIIII'

    headersize = struct.calcsize(headerformat)
    ripentrysize = struct.calcsize(ripentryformat)

    messagelength = len(data)
    numberofentries = int((messagelength - headersize) / ripentrysize)

    rcvtable = []

    header = data[:headersize]
    header = struct.unpack(headerformat, header)
    rcvtable.append(header)

    for i in range(numberofentries):
        start = headersize + ripentrysize * i
        end = headersize + ripentrysize * (i + 1)
        ripentry = data[start:end]
        tableentry = struct.unpack(ripentryformat, ripentry)
        routerid = tableentry[2]
        metric = tableentry[5]
        rcvtable.append([routerid, metric])

    return(rcvtable)


def processrecvtable(data, table):
    '''Takes a recived table and adds it to this routers routing table'''
    # processes recived table : needs updating for new table format
    # validates and adds into this routers table
    # Will need to change when message is changed
    sourcerouter = data[0][2]
    # reset timers for direct neighbour

    # checks for validity

    table[sourcerouter][-1][0] = 0
    table[sourcerouter][-1][1] = 0

    for i in data[1:]:
        routerid = i[0]
        metric = i[1]

        # metric validation
        if metric < 1 or metric > 16:
            print("Metric not in range 0-16")
            continue  # skip this entry

        # update metric
        metric = min(i[1] + table[sourcerouter][1], 16)

        if routerid in table:  # check if update metric
            if table[routerid][0] == sourcerouter:
                table[routerid][-1] = [0, 0]
                table[routerid][1] = metric
                # trigger update if metric different
                if metric == 16:
                    deleteentry(table, routerid)

            elif metric < table[routerid][1]:
                table[routerid] = [sourcerouter, metric, 1, [0, 0]]
                # trigger update

        elif metric < 16:  # add router to table if less than inf
            table[routerid] = [sourcerouter, metric, 1, [0, 0]]
            # trigger update

    return(table)


def deleteentry(table, key):
    '''updates a given key to be marked for deletion'''
    table[key][1] = 16
    table[key][2] = 1
    table[key][3][1] = 120

    return(key)


def garbagecollection(timetaken, table):
    '''if garbage time greater than 0 decrease by time taken and if this reduces it to 0 or below delete
    entry from table'''
    for key in table:
        garbage_timer = table[key][-1][1]

        if garbage_timer > 0:
            garbage_timer -= timetaken
            if garbage_timer <= 0:
                del table[key]


def timeout(timetaken, table):
    '''increment the timeout counters and if it goes above 30 mark for deletion'''
    for key in table:
        route_timer = table[key][-1][0]

        if route_timer < 30:  # Timeout amount
            route_timer += timetaken

        if route_timer >= 30:
            deleteentry(table, key)


# Printer ====================================================

def printtable(table, routerid):
    new_line = (
        "---+++-------+++--------+++------+++-------------+++--------------")
    print("|                    ROUTING TABLE FOR ROUTER {}                    |"
          .format(routerid))
    print(new_line)
    print("ID ||| F_HOP ||| METRIC ||| FLAG ||| GARBTIMEOUT ||| ROUTETIMEOUT ")

    for entry in table:
        print("{}  |||  {}    |||   {}    |||  {}  |||     {}      |||       {}     "
              .format(entry, table[entry][0], table[entry][1], table[entry][2], table[entry][3][0], table[entry][3][1]))
        print(new_line)
    


# Main =======================================================


def main(configfile):
    '''main loop'''

    # setup
    routerid, inputs, outputs = readconfigfile(configfile)
    routingtable = createroutingtable(outputs)
    outputports = outputportdict(outputs)
    start = time.time()

    loop_count = 0
    delay = random.randint(1, 5)

    while True:
        loop_count += 1
        send_message(routingtable, routerid, outputports)
        start = time.time()
        elapsedtime = time.time() - start
        broadcasttime = 5  # Update trigger
        offset = random.randint(-5, 5)
        broadcasttime += offset

        while elapsedtime < broadcasttime:
            start2 = time.time()
            datarecv = listen(inputs)
            if datarecv != 0:
                datarecv = processmsg(datarecv)
                processrecvtable(datarecv, routingtable)
            timetaken = time.time() - start2
            delay = delay - timetaken
            if delay < 0:
                delay = send_message(routingtable, routerid, outputports, 1)
            timetaken = time.time() - start2
            garbagecollection(timetaken, routingtable)
            timeout(timetaken, routingtable)
            elapsedtime += timetaken

        printtable(routingtable, routerid)
    return(None)


# Driver ======================================================
if __name__ == "__main__":
    if len(sys.argv) == 2:
        configfile = sys.argv[1]
        main(configfile)
    else:
        print('This router needs a config file')
        exit()
