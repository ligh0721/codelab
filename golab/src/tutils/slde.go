package tutils

import (
    "encoding/binary"
    "bytes"
    "errors"
)

const SLDE_STX byte = 2
const SLDE_ETX byte = 3
const SLDE_LENGTH_SIZE = 4
const SLDE_HEADER_SIZE = SLDE_LENGTH_SIZE + 1

type Slde struct {
    writebuf *bytes.Buffer
    length int
}

func (self *Slde) Write(data []byte) (int, error) {
    self.writebuf.Write(data)

    if self.writebuf.Len() < SLDE_HEADER_SIZE {
        // header not enough
        return SLDE_HEADER_SIZE - self.writebuf.Len(), nil
    }

    if self.length < 0 {
        // header enough
        var stx byte
        binary.Read(self.writebuf, binary.BigEndian, &stx)
        if stx != SLDE_STX {
            return -1, errors.New("field stx err")
        }
        var length int32
        binary.Read(self.writebuf, binary.BigEndian, &length)
        if length < 0 {
            return -1, errors.New("field length err")
        }
        self.length = int(length)
    }

    left := self.length + 1 - self.writebuf.Len()
    if left > 0 {
        return left, nil
    }

    // write finished
    etx := self.writebuf.Bytes()[self.length]
    if etx != SLDE_ETX {
        return -1, errors.New("field etx err")
    }

    return 0, nil
}

func (self *Slde) Decode() ([]byte, error) {
    if self.length < 0 || self.writebuf.Len() != self.length + 1 {
        println(self.length, self.writebuf.Len())
        return nil, errors.New("data format err")
    }

    return self.writebuf.Bytes()[:self.length], nil
}

func (self *Slde) Encode(data []byte) ([]byte, error) {
    self.length = len(data)
    self.writebuf.Reset()
    binary.Write(self.writebuf, binary.BigEndian, SLDE_STX)
    binary.Write(self.writebuf, binary.BigEndian, int32(self.length))
    self.writebuf.Write(data)
    binary.Write(self.writebuf, binary.BigEndian, SLDE_ETX)
    return self.writebuf.Bytes(), nil
}

func (self *Slde) Bytes() []byte {
    return self.writebuf.Bytes()
}

func (self *Slde) Reset() {
    self.writebuf.Reset()
    self.length = -1
}

func NewSlde() *Slde {
    obj := new(Slde)
    obj.writebuf = bytes.NewBuffer([]byte{})
    obj.length = -1
    return obj
}

func NewSldeWithData(data []byte) *Slde {
    obj := new(Slde)
    obj.writebuf = bytes.NewBuffer([]byte{})
    obj.Encode(data)
    return obj
}