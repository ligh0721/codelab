#!/usr/bin/env python

import struct
import re
import string


class Variable:
    def __init__(self, vtype, name, value = None, upvalue = None):
        self.type = vtype
        self.name = name
        self.value = value
        self.upvalue = upvalue


    def __getitem__(self, k):
        '''var[k]'''
        return self.value[k] and self.value[k].value
        #item = self.item(k)
        #return item and item.value


    def __setitem__(self, k, value):
        '''var[k] = value'''
        if self.value[k]:
            self.value[k].value = value
        #item = self.item(k)
        #if item:
        #    item.value = value
        

    def item(self, k):
        if isinstance(self.value, dict) and not k in self.value:
            print 'ERR | key err, ' + repr(self.value)
            return None
        elif isinstance(self.value, list) and k >= len(self.value):
            print 'ERR | index err, ' + repr(self.value)
            return None

        if self.value[k] == None:
            if isinstance(self.value, dict):
                typeexpr = self.type.ftypeexpr[k]
                ftype = self.type.scope.getType(typeexpr, self)
                var = ftype.allocVar(k)
                var.upvalue = self
                self.value[k] = var
            elif isinstance(self.value, list):
                #print '@@item', k
                var = self.type.itype.allocVar(k)
                var.upvalue = self
                self.value[k] = var
            else:
                return None

        return self.value[k]


    def isStruct(self):
        return isinstance(self.value, dict)


    def isArray(self):
        return isinstance(self.value, list)


    def setValue(self, value):
        self.value = value


    def getValue(self):
        return self.value


    def setUpValue(self, upvalue):
        self.upvalue = upvalue


    def getUpValue(self):
        return self.upvalue


    def encode(self):
        return self.type.encode(self)


    def decode(self, data):
        return self.type.decode(self, data)


    def calcsize(self):
        return self.type.calcsize(self)


    def dump(self, level = 0):
        def addln(s, ln, level):
            if len(s) > 0:
                s += '\n'
            return s + '    ' * level + ln

        res = str()
        if self.isStruct():
            res = addln(res, '\'%s\': {' % (self.name), level)
            first = True
            for name in self.type.fseq:
                fvar = self.value[name]
                if not fvar == None:
                    s = fvar.dump(level = level + 1)
                    if first:
                        first = False
                    else:
                        res += ','
                    res = addln(res, s, 0)
            res = addln(res, '}', level)
        elif self.isArray():
            res = addln(res, '\'%s\': [' % (self.name), level)
            first = True
            for ivar in self.value:
                if not ivar == None:
                    s = ivar.dump(level = level + 1)
                    if first:
                        first = False
                    else:
                        res += ','
                    res = addln(res, s, 0)
            res = addln(res, ']', level)
        else:
            res = addln(res, '\'%s\': %s' % (self.name, repr(self.value)), level)
        
        return res


class Type:
    def __init__(self, scope, name, defval = None):
        self.scope = scope
        self.name = name
        self.defval = defval


    def allocVar(self, name):
        if isinstance(name, str):
            fakename = name.replace('_', 'a')
            if not fakename[0].isalpha() or not fakename.isalnum():
                return None
        elif isinstance(name, int):  # elements of array
            name = '[' + str(name) + ']'
        else:  # failed
            return None

        #print 'DBG | alloc var(%s:%s)' % (name, self.name)
        return Variable(self, name, value = self.defval)


    def encode(self, var, level = 0):
        pass


    def decode(self, var, data, level = 0):
        pass


    def calcsize(self, var):
        pass


class Basic(Type):
    def __init__(self, scope, name, packfmt, defval = None):
        Type.__init__(self, scope, name, defval = defval)
        self.packfmt = packfmt


    def encode(self, var, level = 0):
        print 'E| ' + '    ' * level + '%s %s = %s' % (self.name, var.name, repr(var.value))
        return struct.pack(self.packfmt, var.value)


    def decode(self, var, data, level = 0):
        var.value = struct.unpack_from(self.packfmt, data)[0]
        print 'D| ' + '    ' * level + '%s %s = %s' % (self.name, var.name, repr(var.value))
        return self.calcsize(var)


    def calcsize(self, var):
        return struct.calcsize(self.packfmt)


class String(Basic):
    def __init__(self, scope, size, defval = ''):
        if size == None:
            Basic.__init__(self, scope, 'string()', '', defval = defval)
        else:
            Basic.__init__(self, scope, 'string(%d)' % (size), '%ds' % (size), defval = defval)


    def encode(self, var, level = 0):
        packfmt = self.__packfmt(var)
        print 'E| ' + '    ' * level + '%s %s = %s' % (self.name, var.name, repr(var.value[:int(packfmt[:-1])]))
        return struct.pack(packfmt, var.value)


    def decode(self, var, data, level = 0):
        packfmt = self.__packfmt(var)
        var.value = struct.unpack_from(packfmt, data)[0]
        print 'D| ' + '    ' * level + '%s %s = %s' % (self.name, var.name, repr(var.value[:int(packfmt[:-1])]))
        return self.calcsize(var)


    def calcsize(self, var):
        return struct.calcsize(self.__packfmt(var))


    def __packfmt(self, var):
        if self.packfmt == '':
            return '%ds' % (len(var.value))
        return self.packfmt


class Struct(Type):
    def __init__(self, scope, name, proto):
        '''proto: ((fname, typeexpr), (fname, typeexpr), ...)'''
        Type.__init__(self, scope, name)

        self.fseq = [fname for fname, typeexpr in proto]  # member sequence
        self.ftypeexpr = dict(proto)  # member name-typeexpr map


    def encode(self, var, level = 0):
        print 'E| ' + '    ' * level + '%s %s = {' % (self.name, var.name)
        data = str()
        for fname in self.fseq:
            ftype = self.scope.getType(self.ftypeexpr[fname], var)
            fvar = var.value[fname]
            if fvar == None:  # try to use defval
                fvar = ftype.allocVar(fname)
            res = ftype.encode(fvar, level = level + 1)
            if res == None:
                #print 'ERR | encode:' + fname
                return None
            else:
                data += res
        print 'E| ' + '    ' * level + '}'
        return data


    def decode(self, var, data, level = 0):
        print 'D| ' + '    ' * level + '%s %s = {' % (self.name, var.name)
        pos = 0
        for fname in self.fseq:
            ftype = self.scope.getType(self.ftypeexpr[fname], var)
            fvar = var.value[fname]
            if fvar == None:
                fvar = ftype.allocVar(fname)
                fvar.upvalue = var
                var.value[fname] = fvar
            pos += ftype.decode(fvar, data[pos:], level = level + 1)
        print 'D| ' + '    ' * level + '}'
        return pos


    def calcsize(self, var):
        total = 0
        for fname in self.fseq:
            ftype = self.scope.getType(self.ftypeexpr[fname], var)
            fvar = var.value[fname]
            total += ftype.calcsize(fvar)
        return total


    def allocVar(self, name):
        var = Type.allocVar(self, name)
        if var == None:
            return None

        fvmap = dict()
        for fname in self.fseq:
            fvmap[fname] = None
        
        var.value = fvmap
        return var


class Array(Type):
    def __init__(self, scope, itype, size):
        '''typeexpr: BODY(hdr.result)'''
        Type.__init__(self, scope, '%s[%d]' % (itype.name, size))
        self.itype = itype
        self.size = size


    def encode(self, var, level = 0):
        print 'E| ' + '    ' * level + '%s %s = [' % (self.name, var.name)
        data = str()
        #size = self.scope.getValue(self.sizeexpr, var)
        #itype = self.scope.getType(self.typeexpr, var)
        for index in range(self.size):
            ivar = var.value[index]
            if ivar == None:  # try to use defval
                ivar = self.itype.allocVar(index)
            res = self.itype.encode(ivar, level = level + 1)
            if res == None:
                #print 'ERR | encode:' + fname
                return None
            else:
                data += res
        print 'E| ' + '    ' * level + ']'
        return data


    def decode(self, var, data, level = 0):
        print 'D| ' + '    ' * level + '%s %s = [' % (self.name, var.name)
        pos = 0
        #size = self.scope.getValue(self.sizeexpr, var)
        #itype = self.scope.getType(self.typeexpr, var)
        for index in range(self.size):
            ivar = var.value[index]
            if ivar == None:
                ivar = self.itype.allocVar(index)
                ivar.upvalue = var
                var.value[index] = ivar
            pos += self.itype.decode(ivar, data[pos:], level = level + 1)
        print 'D| ' + '    ' * level + ']'
        return pos


    def calcsize(self, var):
        total = 0
        #size = self.scope.getValue(self.sizeexpr, var)
        #itype = self.scope.getType(self.typeexpr, var)
        for index in range(self.size):
            ivar = var.value[index]
            total += self.itype.calcsize(ivar)
        return total


    def allocVar(self, name):
        var = Type.allocVar(self, name)
        if var == None:
            return None

        var.value = [None] * self.size
        return var


class Scope(Variable):
    def __init__(self, name, parser):
        Variable.__init__(self, None, name, value = dict(), upvalue = None)
        self.parser = parser
        self.tmap = {
            'uint8': Basic(self, 'uint8', 'B', defval = 0),
            'uint16': Basic(self, 'uint16', 'H', defval = 0),
            'uint32': Basic(self, 'uint32', 'I', defval = 0),
            'uint64': Basic(self, 'uint64', 'Q', defval = 0L),
            'int8': Basic(self, 'int8', 'b', defval = 0),
            'int16': Basic(self, 'int16', 'h', defval = 0),
            'int32': Basic(self, 'int32', 'i', defval = 0),
            'int64': Basic(self, 'int64', 'q', defval = 0L),
            'uint16@': Basic(self, 'uint16@', '>H', defval = 0),
            'uint32@': Basic(self, 'uint32@', '>I', defval = 0),
            'uint64@': Basic(self, 'uint64@', '>Q', defval = 0L),
            'int16@': Basic(self, 'int16@', '>h', defval = 0),
            'int32@': Basic(self, 'int32@', '>i', defval = 0),
            'int64@': Basic(self, 'int64@', '>q', defval = 0L)}


    def getVar(self, name):
        if name in self.value:
            return self.value[name]
        return None


    def getType(self, typeexpr, varscope):
        return self.parser.parseType(typeexpr, varscope, 'Scope.getType(%s, %s)' % (repr(typeexpr), varscope.name))
        #try:
        #    return self.parser.parseType(typeexpr, varscope, '')
        #except:
        #    return None


    def getValue(self, expr, varscope):
        return self.parser.parseRValue(expr, varscope, 'Scope.getValue(%s, %s)' % (repr(expr), varscope.name))


    def defType(self, name, proto):
        newtype = Struct(self, name, proto)
        self.tmap[name] = newtype
        return newtype


    def defVar(self, name, typeexpr):
        vtype = self.getType(typeexpr, self)
        if vtype == None:
            return None

        var = vtype.allocVar(name)
        if var == None:
            return None

        var.upvalue = self
        self.value[name] = var
        return var


class State:
    def __init__(self, states, init):
        '''states: {state1, state2, ...}'''
        assert(not None in states and init in states)
        self.states = states
        self.state = init
        self.stack = list()


    def set(self, state):
        '''replace cur state with new state'''
        assert(state in self.states)
        self.state = state


    def get(self):
        assert(self.state != None)
        return self.state


    def push(self, state):
        '''push cur state and set to new state'''
        assert(self.state != None and state in self.states)
        self.stack.append(self.state)
        self.state = state


    def pop(self):
        '''pop state from stack and replace cur state'''
        assert(len(self.stack) > 0)
        self.state = self.stack.pop()


class Parser:
    def __init__(self):
        self.scope = Scope('GLOBAL', self)


    #def getType(self, name):
    #    return self.parseType(self, typeexpr, self.scope, 'Parser.getType(self, %s)' % (repr(name)))


    def getVar(self, expr):
        '''return the Variable instance as a l-value, expr: x or xx.yy.zz'''
        return self.parseLValue(expr, self.scope, 'Parser.getLValue(self, %s)' % (repr(expr)))


    def getValue(self, expr):
        '''return the value of Variable instance as r-value, expr: x or xx.yy.zz'''
        return self.parseRValue(expr, self.scope, 'Parser.getRValue(self, %s)' % (repr(expr)))


    def error(self, e, msg):
        raise e, msg


    def parseLValue(self, expr, varscope, line = ''):
        pass


    def parseRValue(self, expr, varscope, line = ''):
        pass


    def parseType(self, typeexpr, varscope, line = ''):
        pass


class MyParser(Parser):
    def __init__(self):
        Parser.__init__(self)
        self.state = State({'idle'}, 'idle')
        self.keywords = {}
        self.funcions = {
            'import': ('R*', MyParser.func_import),
            'print': ('R*', MyParser.func_print),
            'encode': ('L', MyParser.func_encode),
            'decode': ('LR', MyParser.func_decode),
            'dump': ('L', MyParser.func_dump)
        }


    def parseText(self, text):
        lines = text.splitlines()
        for line in lines:
            self.parseLine(line)


    def parseLine(self, line):
        words = reMyParserParseLine.findall(MyParser.wipeChars(line, ' \t\n\r', '\'\"'))
        if len(words) == 0:
            return

        #print 'DBG | ' + repr(words)
        while len(words) > 0:
            word = words.pop(0)  # pop first word
            if word in self.keywords:  # keyword
                self.error(SyntaxError, '')
                return
            else:  # not a keyword
                if len(words) > 0: # normal statement
                    if words[0] == '=' and len(words) >= 3 and words[2] == ':':  # TYPE = field1:type1 ...
                        tname = word  # type
                        proto = list()
                        while len(words) >= 4:
                            words.pop(0)  # pop = or +
                            fname = words.pop(0)  # pop field name
                            words.pop(0)  #pop :
                            ftypeexpr = words.pop(0)  # pop field typeexpr
                            proto.append((fname, ftypeexpr))
                        
                        if len(proto) == 0 or len(words) > 0:  # failed
                            self.error(SyntaxError, 'invalid syntax: %s' % (repr(line)))
                            return

                        self.scope.defType(tname, proto)
                        #print 'DBG | define type(%s) succ' % (tname)

                    elif words[0] == ':':  # var:TYPE
                        vname = word  # var name
                        words.pop(0)  # pop :
                        if len(words) < 1:  # failed
                            self.error(SyntaxError, 'invalid syntax: %s' % (repr(line)))
                            return

                        vtypeexpr = words.pop(0)  # pop type name
                        var = self.scope.defVar(vname, vtypeexpr)
                        if var == None:  # failed
                            self.error(NameError, 'type(%s) is not defined or cannot be parsed: %s' % (repr(vtypeexpr), repr(line)))
                            return

                        if len(words) > 0:  # var:TYPE = r-value
                            if len(words) != 2 or words[0] != '=':  # failed
                                self.error(SyntaxError, 'invalid syntax: %s' % (repr(line)))
                                return

                            words.pop(0)  # pop =
                            rexpr = words.pop(0)  # pop r-value
                            var.value = self.parseRValue(rexpr, self.scope, line = line)
                        #print 'DBG | define var(%s:%s) succ' % (vname, var.type.name)
                            
                    elif words[0] == '=': # var = value
                        # hdr.len = 5
                        # hdr = pkg.hdr
                        if len(words) != 2:  # failed
                            self.error(SyntaxError, 'invalid syntax: %s' % (repr(line)))
                            return

                        lexpr = word  # l-value
                        words.pop(0)  # pop =
                        rexpr = words.pop(0)  # pop r-value

                        fvar = self.parseLValue(lexpr, self.scope, autoalloc = True, line = line)
                        #flist = lexpr.split('.')
                        #fvar = self.scope
                        #for fname in flist:
                        #    fvar = fvar.item(fname)
                        #    if fvar == None:
                        #        self.error(NameError, 'l-value(%s) cannot be parsed: %s' % (repr(lexpr), repr(line)))
                        #        return

                        fvar.value = self.parseRValue(rexpr, self.scope, line = line)
                    else:  # unsupported syntax
                        self.error(SyntaxError, 'unsupported syntax: %s' % (repr(line)))
                        return

                else:  # var / func(33)
                    expr = word  # expr
                    plists = reBetweenBrackets.findall(expr)
                    if len(plists) == 1:  # func(...)
                        fname = expr[:expr.find('(', 1)]
                        if fname[0] == '(':  # failed
                            self.error(SyntaxError, 'invalid syntax: %s' % (repr(line)))
                            return

                        self.parseFunc(fname, plists[0], line = line)
                    else:  # var
                        self.error(SyntaxError, 'unsupported syntax: %s' % (repr(line)))
                        return


    def parseLValue(self, expr, varscope, autoalloc = False, line = ''):
        flist = expr.split('.')
        if len(flist) == 0 or flist[0] == '' or flist[-1] == '':
            return None

        svar = varscope
        while svar != None:
            # check l1.l2[r1.r2].l3 in varscope
            check = True
            lvar = svar
            lname = None
            lupvar = None
            for name in flist:
                if not lvar.isStruct():
                    check = False
                    break

                indexexprs = reBetweenSqrBrackets.findall(name)
                if len(indexexprs) == 1:  # like .l2[r1.r2]
                    name = name[:name.find('[', 1)]
                    if name[0] == '[':  # failed
                        self.error(SyntaxError, 'invalid syntax: %s' % (repr(line)))
                        return
                if not name in lvar.value:
                    check = False
                    break

                lname = name
                lupvar = lvar
                lvar = lvar.value[name]
                if len(indexexprs) == 1:  # like .l2[r1.r2]
                    index = self.parseRValue(indexexprs[0], varscope, line = line)
                    if index >= len(lvar.value):
                        check = False
                        break

                    lname = index
                    lupvar = lvar
                    lvar = lvar.value[index]

                if lvar == None and autoalloc:
                    if lupvar.isStruct():
                        ltype = self.parseType(lupvar.type.ftypeexpr[lname], lupvar, line = line)
                    elif lupvar.isArray():
                        ltype = lupvar.type.itype
                    lvar = ltype.allocVar(lname)
                    lvar.upvalue = lupvar
                    lupvar.value[lname] = lvar

            if check:
                
                return lvar

            svar = svar.upvalue

        return None


    def parseRValue(self, expr, varscope, line = ''):
        if expr == '':
            #self.error(ValueError, 'nothing to parse: %s' % (repr(line)))
            return None

        # 0 / 128 / 0667 / 0o667 / 0x5dfe / 0b1101 / 'as\ndf' / "ABd\x3fdi\t"
        val = MyParser.toValue(expr)
        if val != None:
            return val

        # ${x + 2}
        if expr[:2] == '${' and expr[-1] == '}':
            try:
                return eval(expr[2:-1])
            except Exception, msg:
                self.error(ValueError, 'eval failed, %s: %s' % (msg, repr(line)))
                return None

        # func(...)
        plists = reBetweenBrackets.findall(expr)
        if len(plists) == 1:  # = func(...)
            fname = expr[:expr.find('(', 1)]
            if fname[0] == '(':  # failed
                self.error(SyntaxError, 'invalid syntax: %s' % (repr(line)))
                return
            return self.parseFunc(fname, plists[0], line = line)

        # datalen / hdr2.data.len
        lvar = self.parseLValue(expr, varscope, line = line)
        if lvar != None:
            return lvar.value  # return r-value

        self.error(ValueError, 'r-value(%s) cannot be parsed: %s' % (repr(expr), repr(line)))
        return None


    def parseFunc(self, fname, paramexprs, line = ''):
        if not fname in self.funcions:  # function not defined
            self.error(NameError, 'function(%s) is not defined: %s' % (repr(fname), repr(line)))
            return None

        fparamlr, func = self.funcions[fname]
        paramlist = paramexprs.split(',')
        vals = list()
        if fparamlr[-1] != '*':  # use MIN(paramlist.size, fparamlr.size)
            paramlist = paramlist[:len(fparamlr)]

        lrlock = None
        for index, paramexpr in enumerate(paramlist):
            lr = None

            if lrlock == None:
                lr = fparamlr[index]
                if lr == '*':
                    lrlock = fparamlr[index - 1]
                    lr = lrlock
            else:
                lr = lrlock

            val = None
            if lr == 'L':  # function accept a l-value
                val = self.parseLValue(paramexpr, self.scope, line = line)
            elif lr == 'R':  # function accept a r-value
                val = self.parseRValue(paramexpr, self.scope, line = line)
            else:  # unsupported function proto
                self.error(SyntaxError, 'unsupported function proto(%s): %s' % (repr(fparamlr), repr(line)))
                return None

            if val == None:  # failed
                self.error(ValueError, 'invalid value: %s' % (repr(line)))
                return None

            vals.append(val)
        return func(*vals)


    def parseType(self, typeexpr, varscope, line = ''):
        '''for example, typeexpr: BODY(hdr.result), varscope: pkg
        PKG = hdr:HDR + body:BODY(hdr.result)
        hdr is in pkg, so the varscope is pkg'''
        # vtype[expr] / vtype(expr2)[expr1]
        exprs = reBetweenSqrBrackets.findall(typeexpr)
        if len(exprs) == 1:
            vtype = typeexpr[:typeexpr.find('[', 1)]
            if vtype[0] == '[':
                self.error(SyntaxError, 'invalid syntax: %s' % (repr(line)))
                return None

            vtype = self.parseType(vtype, varscope, line = line)

            val = self.parseRValue(exprs[0], varscope, line = line)
            if isinstance(val, int):
                return Array(self.scope, vtype, val)
            else:
                self.error(ValueError, 'value(%s) is not an integer: %s' % (repr(exprs[0]), repr(line)))
                return None

        # vtype(expr)
        exprs = reBetweenBrackets.findall(typeexpr)
        if len(exprs) == 1:
            vtype = typeexpr[:typeexpr.find('(', 1)]
            if vtype[0] == '(':
                self.error(SyntaxError, 'invalid syntax: %s' % (repr(line)))
                return None

            val = self.parseRValue(exprs[0], varscope, line = line)
            if isinstance(val, dict) or isinstance(val, list):  # struct value
                self.error(ValueError, 'invalid value(%s): %s' % (repr(exprs[0]), repr(line)))
                return None

            if vtype in ('string'):
                if isinstance(val, int) or exprs[0] == '':
                    return String(self.scope, val)
                else:
                    self.error(ValueError, 'value(%s) is not an integer: %s' % (repr(exprs[0]), repr(line)))
                    return None

            if val == None:
                self.error(ValueError, 'value(%s) cannot be parsed: %s' % (repr(exprs[0]), repr(line)))
                return None

            typeexpr = vtype + '(' + repr(val) + ')'

            if typeexpr in self.scope.tmap:
                return self.scope.tmap[typeexpr]
            else:
                typeexpr = vtype + '()'

        if typeexpr in self.scope.tmap:
            return self.scope.tmap[typeexpr]

        #print 'ERR | typeexpr(%s)' % (typeexpr)
        self.error(NameError, 'type(%s) is not defined or cannot be parsed: %s' % (repr(typeexpr), repr(line)))
        return None


    @staticmethod
    def wipeChars(s, chars, bchars):
        lst = list()
        sep = None
        for c in s:
            if sep == None and c in bchars:  # ' or "
                sep = c
                lst.append(c)
                continue

            if sep != None or not c in chars:
                lst.append(c)

            if c == sep:
                sep = None
                
        return ''.join(lst)


    @staticmethod
    def toValue(s):
        # 0 / 128 / 0667 / 0o667 / 0x5dfe / 0b1101
        base = 10
        prefix = s[:2]
        if s.isdigit():
            if s[0] == '0':
                base = 8
            else:
                base = 10
        elif prefix == '0x':
            base = 16
        elif prefix == '0b':
            base = 2
        elif prefix == '0o':
            base = 8
        try:
            return int(s, base)
        except:
            # 'adff' / "fapsdf"
            if (s[0] == '\'' or s[0] == '\"') and s[0] == s[-1]:
                return eval(s)

        return None


    @staticmethod
    def func_import(*rmods):
        for rmod in rmods:
            exec('import ' + rmod)

    
    @staticmethod
    def func_print(*rvals):
        for rval in rvals:
            print rval,
        print


    @staticmethod
    def func_encode(lvar):
        return lvar.encode()


    @staticmethod
    def func_decode(lvar, rdata):
        return lvar.decode(rdata)


    @staticmethod
    def func_dump(lvar):
        return lvar.dump()
        
        
reBetweenBrackets = re.compile(r'\((.*)\)')
reBetweenSqrBrackets = re.compile(r'\[(.*)\]')
reEval = re.compile(r'${(.*)}')
#reMyParserParseLine = re.compile(r'\'.*\'|".*"|[+=:]|[\w_.(),]+')
reMyParserParseLine = re.compile(r'".*"|[+=:]|[\w_(){}\[\]$.\',@]+')

p = MyParser()
scope = p.scope

p.parseLine(r'HDR = len:uint16 + result:uint8')
p.parseLine(r'BODY(0) = data:string(hdr.len) + crc:string(4)')
p.parseLine(r'BODY(1) = msg:string(10)')
p.parseLine(r'PKG = flag:uint8 + hdr:HDR + body:BODY(hdr.result)')
p.parseLine(r'pkg: PKG')
p.parseLine(r'pkg.flag = ${max(123, 222)}')
p.parseLine(r'hdr: HDR')
p.parseLine(r'hdr.len = 6')
p.parseLine(r'hdr.result = 0')
p.parseLine(r'pkg.hdr = hdr')
p.parseLine(r'pkg.body.data = "what is your name?"')
p.parseLine(r'pkg.body.crc = "\xAA\xBB\xCC\xDD"')
p.parseLine(r's:string() = encode(pkg)')
#p.parseLine(r's = dump(pkg)')
#p.parseLine(r's = encode(pkg)')
#p.parseLine(r'print(s)')
p.parseLine(r'pkg2: PKG')
p.parseLine(r'decode(pkg2,s)')
p.parseLine(r's = dump(pkg2)')
p.parseLine(r'print(s, 5454)')
#p.parseLine(r's = dump(s)')
#p.parseLine(r'print(s)')

text = r'''
PNG_CHUNK = Length:uint32@ + Type:string(4) + Data:PNG_DATA(Type) + CRC:uint32@
PNG_DATA('IHDR') = Width:uint32@ + Height:uint32@ + BitDepth:uint8 + ColorType:uint8 + CompressionMethod:uint8 + FilterMethod:uint8 + InterlaceMethod:uint8
PNG_DATA() = data:string(Length)
PNG = sig:string(8) + chunks:PNG_CHUNK[2]

png:PNG
chunk:PNG_CHUNK

arr:int32[4]
arr[2] = 3
arr[0] = 5
print(dump(arr))

arr:string()[3]
arr[0] = ${hex(18)}
arr[2] = "gogogo~~!!!"
print(dump(arr))
print(encode(arr))
import('os', 'sys')
print(${os.path.sep})
'''
p.parseText(text)

f = open('test.png', 'rb')
data = f.read()
f.close()

png = p.getVar('arr[2]')
#png.decode(data)

print png.dump()
