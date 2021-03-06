#!/usr/bin/env python

import socket
import select


class FwIpPort:
    def __init__(self):
        self.sck = None
        self.regs = dict()  # {sIp: (daddr, hook), ...}

    def register(self, sIp, daddr, hook=None):
        '''sIp can be '0.0.0.0' for accept all connections
        hook function is like hook(data, **args), args: fromaddr, toaddr, fromissrc
        '''
        if sIp in self.regs:
            print 'D|rule(%s, %s:%d) has been existed, updated' % ((sIp,) + daddr)
        self.regs[sIp] = (daddr, hook)

    def start(self, bindaddr):
        pass

class FwTcpPort(FwIpPort):
    def __init__(self):
        FwIpPort.__init__(self)
        self.sscks = None
        self.dscks = None

    def start(self, bindaddr, reuseaddr=False):
        self.sck = socket.socket(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP)
        if reuseaddr:
            self.sck.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.sck.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        try:
            self.sck.bind(bindaddr)
        except Exception, msg:
            print 'D|bind|%s' % (msg,)
            self.sck.close()
            return

        self.sck.listen(5)
        self.sscks = dict()  # {ssck:(dsck, saddr), ...}
        self.dscks = dict()  # {dsck:(ssck, daddr), ... }
        while True:
            torlist = [self.sck]
            while True:
                rlist, wlist, xlist = select.select(torlist, list(), list(), 1)
                for rsck in rlist:
                    if rsck is self.sck:  # listen sock
                        ssck, saddr = rsck.accept()
                        print 'D|accept'
                        daddr, hook = None, None
                        if not saddr[0] in self.regs:  # unregistered addr
                            if '0.0.0.0' in self.regs:
                                daddr, hook = self.regs['0.0.0.0']
                        else:
                            daddr, hook = self.regs[saddr[0]]
                        
                        if daddr == None:
                            print 'D|accept src|unregistered addr(%s:%d)' % saddr
                            ssck.close()
                            continue

                        dsck = socket.socket(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP)
                        try:
                            dsck.connect(daddr)
                        except Exception, msg:
                            print 'D|connect dst|%s' % (msg,)
                            ssck.close()
                            dsck.close()
                            continue
                        
                        torlist.append(ssck)
                        torlist.append(dsck)
                        self.sscks[ssck] = (dsck, saddr)
                        self.dscks[dsck] = (ssck, daddr)
                        print 'D|add pair|%s:%d -> %s:%d' % (saddr + daddr)

                    else:  # src sock or dst sock
                        data = rsck.recv(0xffff)
                        wsck, raddr = None, None
                        rsck_, waddr = None, None  # debug
                        saddr, riss = None, None  # is reading src sock
                        if rsck in self.sscks:
                            riss = True
                        elif rsck in self.dscks:
                            riss = False
                        else:
                            assert(False and 'Impossible!')

                        if not data:  # connection closed
                            if riss:  # src sock closed
                                wsck, raddr = self.sscks.pop(rsck)
                                rsck_, waddr = self.dscks.pop(wsck)  # debug
                                saddr = raddr
                            else:  # dst sock closed
                                wsck, raddr = self.dscks.pop(rsck)
                                rsck_, waddr = self.sscks.pop(wsck)  # debug
                                saddr = waddr
                            assert(rsck_ is rsck)  # debug

                            torlist.remove(rsck)
                            torlist.remove(wsck)
                            if rsck in rlist:
                            	rlist.remove(rsck)
                            if wsck in rlist:
                            	rlist.remove(wsck)

                            daddr, hook = (saddr[0] in self.regs and self.regs[saddr[0]]) or self.regs['0.0.0.0']
                            if hook != None:
                                hook(data, fromaddr = raddr, toaddr = waddr, fromissrc = riss)

                            rsck.close()
                            wsck.close()

                            print 'D|del pair'

                        else:  # forward data
                            if riss:  # src sock -> dst sock
                                wsck, raddr = self.sscks[rsck]
                                rsck_, waddr = self.dscks[wsck]  # debug
                                saddr = raddr
                            else:  # dst sock -> src sock
                                wsck, raddr = self.dscks[rsck]
                                rsck_, waddr = self.sscks[wsck]  # debug
                                saddr = waddr
                            assert(rsck_ is rsck)

                            daddr, hook = (saddr[0] in self.regs and self.regs[saddr[0]]) or self.regs['0.0.0.0']
                            if hook != None:
                                data = hook(data, fromaddr = raddr, toaddr = waddr, fromissrc = riss) or data

                            wsck.send(data)

        self.sck.close()


def main():
    import sys

    fwp = FwTcpPort()
    if len(sys.argv) <= 1:  # example
        def httphook(data, **args):
            fromaddr = args['fromaddr']
            fromissrc = args['fromissrc']
            if fromissrc:
                datalines = data.splitlines()
                for index, line in enumerate(datalines):
                    if line[:6] == 'Host: ':
                        datalines[index] = 'Host: idea.iteblog.com'
                data = '\r\n'.join(datalines) + '\r\n'

            print data
            return data

        bindaddr = ('0.0.0.0', 80)
        fwp.register('0.0.0.0', ('idea.iteblog.com', 80), hook=httphook)
    else:
        bindaddr = (sys.argv[1], int(sys.argv[2]))
        for i in xrange(3, len(sys.argv), 3):
            fwp.register(sys.argv[i], (sys.argv[i + 1], int(sys.argv[i + 2])))

    fwp.start(bindaddr, reuseaddr=True)


if __name__ == '__main__':
    main()

