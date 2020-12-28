#
#   Copyright (c) 2020 Christof Ruch. All rights reserved.
#
#   Dual licensed: Distributed under Affero GPL license by default, an MIT license is available for purchase
#


def name():
    return "Sequential Prophet 6"  # Sequential product name is Prophet-6


def createDeviceDetectMessage(channel):
    # This is a sysex generic device detect message
    return [0xf0, 0x7e, channel, 0x06, 0x01, 0xf7]


def deviceDetectWaitMilliseconds():
    return 100


def needsChannelSpecificDetection():
    return False


def channelIfValidDeviceResponse(message):
    if (len(message) > 9
            and message[0] == 0xf0  # Sysex
            and message[1] == 0x7e  # Non-realtime
            and message[3] == 0x06  # Device request
            and message[4] == 0x02  # Device request reply
            and message[5] == 0x01  # Sequential / Dave Smith Instruments
            and message[6] == 0b00101101  # Prophet 6
            and message[7] == 0x01  # Familiry MS
            and message[8] == 0x00  # Family
            and message[9] == 0x00):  # Family
        # Extract the current MIDI channel from index 2 of the message
        return message[2]
    return -1


def createEditBufferRequest(channel):
    return [0xf0, 0x01, 0b00101101, 0b00000110, 0xf7]


def isEditBufferDump(message):
    return (len(message) > 3
            and message[0] == 0xf0
            and message[1] == 0x01  # Sequential
            and message[2] == 0b00101101  # Prophet 6
            and message[3] == 0b00000011  # Edit Buffer Data
            )


def numberOfBanks():
    return 10


def numberOfPatchesPerBank():
    return 100


def createProgramDumpRequest(channel, patchNo):
    bank = patchNo // numberOfPatchesPerBank()
    program = patchNo % numberOfPatchesPerBank()
    return [0xf0, 0x01, 0b00101101, 0b00000101, bank, program, 0xf7]


def isSingleProgramDump(message):
    return (len(message) > 3
            and message[0] == 0xf0
            and message[1] == 0x01  # Sequential
            and message[2] == 0b00101101  # Prophet 6
            and message[3] == 0b00000010  # Program Data
            )


def nameFromDump(message):
    dataBlock = []
    if isSingleProgramDump(message):
        dataBlock = message[6:-1]
    elif isEditBufferDump(message):
        dataBlock = message[4:-1]
    if len(dataBlock) > 0:
        patchData = unescapeSysex(dataBlock)
        return ''.join([chr(x) for x in patchData[107:127]])
    return "Invalid"


def convertToEditBuffer(channel, message):
    if isEditBufferDump(message):
        return message
    elif isSingleProgramDump(message):
        # Have to strip out bank and program, and set command to edit buffer dump
        return message[0:3] + [0b00000011] + message[6:]
    raise Exception("Neither edit buffer nor program dump - can't be converted")


def convertToProgramDump(channel, message, program_number):
    bank = program_number // numberOfPatchesPerBank()
    program = program_number % numberOfPatchesPerBank()
    if isEditBufferDump(message):
        return message[0:3] + [0b00000010] + [bank, program] + message[4:]
    elif isSingleProgramDump(message):
        return message[0:3] + [0b00000010] + [bank, program] + message[6:]
    raise Exception("Neither edit buffer nor program dump - can't be converted")


def unescapeSysex(sysex):
    result = []
    dataIndex = 0
    while dataIndex < len(sysex):
        msbits = sysex[dataIndex]
        dataIndex += 1
        for i in range(7):
            if dataIndex < len(sysex):
                result.append(sysex[dataIndex] | ((msbits & (1 << i)) << (7 - i)))
            dataIndex += 1
    return result
