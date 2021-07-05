def routing_table(filenm):
    ''' Reads the config from the config file and builds the routing table
        from it.
        @param filename: name of the config file to read '''
    global own_id
    total = []
    table = {}
    c1=open(filenm, 'r')
    for i in c1.readlines():
        i=i.split(', ')
        total.append(i)

    own_id = int(total[0][1])
    inputs_length = len(total[1])
    outputs_length = len(total[2])


    for i in range(1, inputs_length):
        input_ports.append(int(total[1][i]))


    for i in range(1,outputs_length):
        temp = total[2][i]
        temp = temp.split('-')
        router_id = int(temp[2])
        portno = int(temp[0])
        output_ports[portno] = router_id
        first_router = router_id
        metric = int(temp[1])
        flag = False
        timers = [0, 0]

        # Layout of this table is [ID: [FIRST-ROUTER,COST,FLAG,TIMER]]
        table[router_id] = [first_router, metric, flag, timers]
    #     print("Output Ports: " + str(output_ports))
    #     print_table(table)
    #     print("----- Finished reading configuration file.\n")
    return table




def listenlist():
    '''Creates and binds input_ports to sockets'''

    sock_list=[]
    for i in range(0, len(input_ports)):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(('', int(input_ports[i]) ))
        sock_list.append(sock)
    return sock_list

'''Jacobs new fuctions, needs error checks still'''
def readconfigfile(configfilename):
    '''Takes a config file and returns the routerid list of input ports and list of outputs'''

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

    #print(routerid)
    #print(inputports)
    #print(outputs)

    return(routerid, inputports, outputs)


def createroutingtable(outputs):
    table = {}
    flag = False
    timers = [0, 0]

    for output in outputs:
        routerid = output[2]
        firstrouter = routerid
        distance = output[1]
        table[routerid] = [firstrouter, distance, flag, timers]

    return(table)


def outputportdict(outputs):
    outputports = {}
    for output in outputs:
        outputports[output[0]] = output[2]

    return(outputports)

# =============================================================
# receiver: Needs more editing with message changes
# listens on all input sockets for a message and then processes that message. can be split into reciving and processing
def create_message(table, routerid):
    ''' Creates message with information about
        @param t: dictionary representing the routing table
        @param port: port number that it is being sent to so that we can
                     exclude entries.
    '''
    headerformat = '!BBH'
    ripentryformat = '!HHIIII'
    command = 2  # Command response message
    version = 2  # rip version
    header = struct.pack(headerformat, command, version, routerid)

    for i in table:
        value = table[i]
        metric = value[1]
        afi = 0
        ripentry = struct.pack(ripentryformat, afi, 0, i, 0, 0, metric)
        header += ripentry

    return header

def receiver(table, timeout):
    ''' Checks the sockets to see if any messages have been received.
        @param rt_table: dictionary representing the routing table
    '''

    socket_list = listenlist()  # binds and listens to inputsockets
    table_key = []
    sockets, b, c = select.select(socket_list, [], [], timeout)
    if sockets != []:
        s = sockets[0]
        s.settimeout(10)
        data, addr = s.recvfrom(1024)


    return(data)


def processmsg(data):
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
    # processes recived table : needs updating for new table format
    # validates and adds into this routers table
    # Will need to change when message is changed

    # reset timers for direct neighbour
    table[src][-1][0] = 0
    table[src][-1][1] = 0
    table[src][2] = False

    start = 3  # start of table in message
    src = int(data[2])  # data sorce
    while start < len(data):
        rec_id = int(data[start])
        router_id = int(data[start])

        # validates metric
        if metric not in range(0, 17):  # fix
            print("Packet does not conform. Metric not in range 0-16")
            break

        # update metric
        metric = min(int(data[start + 1]) + table[src][1], 16)

        # validates id and adds to table
        if router_id not in output_ports.values() and router_id != own_id:
            if not id_in_list(rec_id, table):
                table[router_id] = [src, metric, False, [0, 0]]

            if (metric < table[router_id][1]):
                # better route has been found
                table[router_id][1] = metric
                table[router_id][0] = src

            if (src == table[router_id][0]):
                # Submitting to the information the router gives us if they
                # are the first hop to the destination.
                table[router_id][1] = metric
                table[router_id][0] = src
                table[router_id][-1][0] = 0  # Reset Timer
                table[router_id][-1][1] = 0
                table[router_id][2] = False

        start += 2

    return(table)


def router_keys(table):
    ''' returns keys grabbed from the route table
    '''
    route_keys=[]
    try:
        for y in table.keys():
            route_keys.append(y)
        return route_keys
    except:
        return route_keys

