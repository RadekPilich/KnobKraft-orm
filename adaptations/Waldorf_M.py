#
#   Copyright (c) 2025 Christof Ruch. All rights reserved.
#
#   Dual licensed: Distributed under Affero GPL license by default, an MIT license is available for purchase
# https://gearspace.com/board/attachments/electronic-music-instruments-and-electronic-music-production/1119908d1719787216-waldorf-m-synthesizer-m-sysex-rev-02.pdf
# https://github.com/eclab/edisyn/blob/master/edisyn/synth/waldorfm/WaldorfM.java#L1952

#--------------------------------------------- IMPORT
import hashlib
from copy import copy
from typing import List, Optional

from BACKUP.Waldorf_M import WALDORF_M
import testing
import string
import time
#--------------------------------------------- ADOPTION

def name():
    return "Waldorf M"

def setupHelp():
    return "Waldorf M has two relevant global settings necessary to operate with KnobKraft:\n" \
        "------------------------------------------------------------------------------------------------ \n" \
        "1. You must allign the MIDI channel on synth and the adaption (def adaptChannel in 0-15 numbering)\n\n" \
        "2. You must set PC/BC Filter to NO\n\n" \
        "Both settings are accessible via the GLOBALS menu.\n\n" \
        "Remember to store the settings before exiting the menu!\n\n\n" \
        "Waldorf M adaption considerations:\n" \
        "---------------------------------------- \n" \
        "1. Channel cannot be detected - set it manually via def adaptChannel().\n\n" \
        "2. Currently the bytes for bank an program number are not populated in SySex, therefore dump responses are effectively edit buffer dumps and numberFromDump cannot be acquired from SySex messages. Therefore a workaround with global variable progDumpNo, that counts the programs during a bank dump. \n\n" \
        "3. Synth bank numbering with regards to bank change is 1-based - byte value for Bank 00 is 1.\n\n" \
        "4. Multi bank is included in the adaption as the first bank (index zero). This effectively alligns indexes of KnobKrafts banks with bank byte numbers on synth - both index and bank byte number for the Bank 00 is 1.\n\n\n" \
        "Dealing with slowness of the synth:\n" \
        "---------------------------------------- \n" \
        "5. Program and buffer dumps onto the synth work normally, except it takes M roughly 7 seconds to store a patch, therefore patchStoreWait() function. Increase the wait time by a second or two in case some patches from dump are not stored on the synth. It doesn't seem necessary to set different times for single and multi dumps.\n\n" \
        "6. Similar to above -  multiDumpWait() function is used to set delay between Multi program changes when downloading Multis into KnobKraft. Time around 500 ms seems to be enough. If it is too short for the synth, it will skip downloading some slots.\n\n" \
        "7. The Wait functions effectively pause the KnobKraft createDumpRequest cycles rather then overriding the generalMessageDelay. This is done because we are sending a series of messages during the requests in order to automate single / multi mode switching and we don't need delay between individual messages, we need delay between programs.\n\n" \

def numberOfBanks():
    return 1+16

def numberOfPatchesPerBank():
    return 128
    
def adaptChannel():
    return 1             # 0-based, so 1 means channel 2 on the synth

def bankDescriptors():
    return [{"bank": x, "name": f"Multi Bank A", "size": 128, "type": "Arrangement"} for x in range(1)] + [{"bank": x, "name": f"Bank {(x-1):02d}", "size": 128, "type": "Patch"} for x in range(1,17)]

def bankSelect(channel, bank):
    if bank == 0: #multi
        #byte 5 - arrangement to load 0-127  byte 6 - ignored byte 7 - ignored
        return [0xf0, WALDORF_ID, WALDORF_M, 0x00, CHANGE_MODE, 0x01, 0x00, 0x00, 0xf7]
    return [0xf0, WALDORF_ID, WALDORF_M, 0x00, CHANGE_MODE, 0x00, 0x00, 0x00, 0xf7] + [0xb0|(channel & 0x0f), 32, bank-1]

def createCustomProgramChange(channel, patchNo):
    bank = patchNo // numberOfPatchesPerBank()
    program = patchNo % numberOfPatchesPerBank()
    if bank == 0: #multi
            # switch to multi + change arrangement
            return [0xf0, WALDORF_ID, WALDORF_M, 0x00, CHANGE_MODE, 0x01, 0x00, 0x00, 0xf7] + [0xf0, WALDORF_ID, WALDORF_M, 0x00, CHANGE_MULTI, program, 0x00, 0x00, 0xf7]
   #switch to single + change bank + change program
    return [0xf0, WALDORF_ID, WALDORF_M, 0x00, CHANGE_MODE, 0x00, 0x00, 0x00, 0xf7] + [0xb0|(channel & 0x0f), 32, bank-1] + [0xc0|(channel & 0x0f), program]

def friendlyBankName(bank):
    if bank == 0: #multi
        return f"MA-"
    if bank == numberOfBanks(): #multi DB
        return f"MX-"
    if bank > numberOfBanks(): #single DB
        return f"X-"
    return f"{str(bank-1).zfill(2)}" #single

def friendlyProgramName(patchNo):   # Pad with leading zeros to make it match the display
    program = patchNo % numberOfPatchesPerBank()
    bank = patchNo // numberOfPatchesPerBank()
    if bank == 0:  #multi
        return "%s%s" % (friendlyBankName(bank), str(program + 1).zfill(3))
    return "%s%s" % (friendlyBankName(bank), str(program + 1).zfill(3))

#--------------------------------------------- DETECTION

#-----------------------SYSEX COMMON HEADER 
WALDORF_ID = 0x3e       # message[1] 
WALDORF_M = 0x30        # message[2] 
                        # message[3] 

#-----------------------SYSEX MSG ID = message[4] 
CHANGE_MULTI = 0x66     #Request Multi Arrangement Change
CHANGE_MODE = 0x64      #Request Mode Change
PRESS_BUTTON = 0x62     #Request Button Press
                        #Request Active Sound Parameter 0x70
                        #Dump Active Sound Parameter 0x71
REQUEST_SINGLE = 0x74   #Request Single Sound 0x74
DUMP_SINGLE = 0x72      #Dump Single Sound 0x72
                        #Request Active Multi Parameter 0x7A
                        #Dump Multi Parameter 0x7B
REQUEST_MULTI = 0x75    #Request Multi Arrangement 0x75
DUMP_MULTI = 0x73       #Dump Multi Arrangement 0x73
                        #Request System Parameter 0x7C
                        #Dump Global Parameter 0x7D
                        
# Single and Multi dumps are regular straightforward full patch dumps. The parameter dumps however are single parameter dumps via MSB / LSB bytes. This is for remote SysEx control of the synth. Full details are in the M sysex documentaiton.

def createDeviceDetectMessage(channel):
    # Just request the edit buffer - allegedly, it does not use the device id so that could be quick
    # The parameter is ignored, it defaults to 0x7f 127 when it hasn't been detected yet
    return createEditBufferRequest(127)

def needsChannelSpecificDetection():
    return False

def deviceDetectWaitMilliseconds():
    return 1000

def generalMessageDelay():
    return 200
    
def patchStoreWait():           # Due to littleFS used on internal flash, the save speeds are really slow (cost of longevitiy)
    return time.sleep(7)

def multiDumpWait():
    return time.sleep(0.5)

def channelIfValidDeviceResponse(message):
    channel = adaptChannel()
    DEVICE_ID_DETECTED = message[3]
    if isEditBufferDump(message):
        print(f"Waldorf M has been detected as Device_Id {DEVICE_ID_DETECTED}. The adaption code is set to use MIDI channel {channel+1}.")
        return channel
    return -1
    
#--------------------------------------------- PROGRAM NUMBER & NAME

nameBaseIndex = 6 #
nameLength = 26 # 26 total, 22 visible on store screen, 23 editable on store screen, 16 visible on home screen.... seriously Vladis?
characterSet = string.ascii_letters + string.digits  + ' .!@#$%&*()_+-=' + '\0'

def patchNoOffsetToggle():
    return True

 # patchNoOffsetToggle set to True shifts patchNo stored in DB beyond the logical limit of the synth bank sequence (banks*patches per bank)
 # patchNo is overridden by the sequence in In Synth lists or User Bank lists to contain information about TARGET program and bank location
 # we use patchNo above upper synth sequence limit for Imports to give information only about program - imported program from slot 23 will have the same patchNo no matter if pulled from bank 1 or bank 11.
 # first 128 offset patchNo are for multis, second 128 offset patchNo are for single programs
 # This makes possible differentiating friendlyBankName properly - "bank-less" for patches in DB and "bank-specifc" for lists

def multiNoOffset():
    if patchNoOffsetToggle() is True:
        return numberOfBanks() * numberOfPatchesPerBank()
    return 0

def patchNoOffset():
    if patchNoOffsetToggle() is True:
        return multiNoOffset() + numberOfPatchesPerBank()
    return 0

def numberFromDump(message) -> int:
    global progDumpNo  # see comments in the PROGRAM DUMP section - this is a workaround to get the program number from dumps until the synth starts filling it in message[33].
    multi = multiNoOffset() + progDumpNo
    single = patchNoOffset() + progDumpNo
    if isEditBufferDump(message) or isSingleProgramDump(message):
        if message[4] == DUMP_MULTI: #multi
            return multi
        return single

def nameFromDump(message: List[int]) -> str:
    if isEditBufferDump(message) or isSingleProgramDump(message):
        return ''.join([chr(x) for x in message[nameBaseIndex:nameBaseIndex+nameLength]]).replace('\0', '').strip()
    return "invalid"

def renamePatch(message, new_name):
    if isEditBufferDump(message) or isSingleProgramDump(message):
        clean_name = new_name.strip()[:nameLength].ljust(nameLength, '\0')
        valid_name = [ord(x) if x in characterSet else ord('_') for x in clean_name]
        return message[:nameBaseIndex] + valid_name + message[nameBaseIndex + nameLength:]
    raise Exception("Neither edit buffer nor program dump can't be converted")

#--------------------------------------------- EDIT BUFFER

def createEditBufferRequest(channel, patchNo):
    bank = patchNo // numberOfPatchesPerBank()
    program = patchNo % numberOfPatchesPerBank()
    if bank == 0: #multi
        [0xf0, WALDORF_ID, WALDORF_M, 0x00, REQUEST_MULTI, 0x00, 0x00, 0x00, 0xf7]
    return [0xf0, WALDORF_ID, WALDORF_M, 0x00, REQUEST_SINGLE, 0x00, 0x00, 0x00, 0xf7]

def isEditBufferDump(message: List[int]) -> bool:
    return (len(message) == 512 #single
            and message[0] == 0xf0
            and message[1] == WALDORF_ID
            and message[2] == WALDORF_M
            and message[4] == DUMP_SINGLE) + (len(message) == 320 #multi
            and message[0] == 0xf0
            and message[1] == WALDORF_ID
            and message[2] == WALDORF_M
            and message[4] == DUMP_MULTI)

def convertToEditBuffer(channel, message):
    if isEditBufferDump(message) or isSingleProgramDump(message):
        new_message = copy(message)
        if len(message) == 512: #single
            new_message[3] = 0x00
            new_message[4] = DUMP_SINGLE
            new_message[32] = 0x00 
            new_message[33] = 0x00
            new_message[34] = 0x01  # Setting this to 1 says "Do not save"
            new_message[35] = 0x00
            return [0xf0, WALDORF_ID, WALDORF_M, 0x00, CHANGE_MODE, 0x00, 0x00, 0x00, 0xf7] + new_message
        if (len(message) == 320): #multi
            new_message[3] = 0x00
            new_message[4] = DUMP_MULTI
            new_message[32] = 0x01  # exact (0-1) f exact = 1 the M will save an arrangement dump into the slot, defined by next byte (slot)
            new_message[33] = 0x7f  # slot (0-127) - we choose 127 as the best slot for mutli pseudo-edit buffer storage    
            new_message[34] = 0x00  # Setting this to 0 says "Save" - multis have to be stored, there is not slot-less edit buffer 
            new_message[35] = 0x00
            # change to multi + change arrangement to 127 = our multi edit buffer slot + send the edit buffer dump to store it there, M consequently recalls it
            return [0xf0, WALDORF_ID, WALDORF_M, 0x00, CHANGE_MODE, 0x01, 0x00, 0x00, 0xf7] + [0xf0, WALDORF_ID, WALDORF_M, 0x00, CHANGE_MULTI, 0x7f, 0x00, 0x00, 0xf7] + new_message
    raise Exception("Can only convert edit buffers or single programs")

#--------------------------------------------- PROGRAM DUMP

def createProgramDumpRequest(channel, program_number):
    global progDumpNo
    progDumpNo = -1 # This is a workaround to get the program number from dumps until the synth starts filling it in message[33]. It relies on the fact that program dumps are pulling a whole bank. We reset the counter before the full bank pull, then increment it for each program decoded from dump.
    bank = program_number // numberOfPatchesPerBank()
    program = program_number % numberOfPatchesPerBank()
    if bank == 0: #multi
        multiDumpWait()          # Wait between requests for M to finish changing arrangements
        return [0xf0, WALDORF_ID, WALDORF_M, 0x00, CHANGE_MODE, 0x01, 0x00, 0x00, 0xf7] + [0xf0, WALDORF_ID, WALDORF_M, 0x00, REQUEST_MULTI, 0x00, program, 0x00, 0xf7]      
    return [0xf0, WALDORF_ID, WALDORF_M, 0x00, CHANGE_MODE, 0x00, 0x00, 0x00, 0xf7] + [0xf0, WALDORF_ID, WALDORF_M, 0x00, REQUEST_SINGLE, 0x00, bank, program, 0xf7]

def isSingleProgramDump(message: List[int]) -> bool:
    global progDumpNo # This works hand in hand with createProgramDumpRequest 
    if ((len(message) == 512 or len(message) == 320)
    and message[0] == 0xf0
    and message[1] == WALDORF_ID
    and message[2] == WALDORF_M
    and (message[4] == DUMP_SINGLE or message[4] == DUMP_MULTI)) > 0:
        if progDumpNo > 127: 
            progDumpNo = -1
        progDumpNo += 1
    return ((len(message) == 512 or len(message) == 320)
            and message[0] == 0xf0
            and message[1] == WALDORF_ID
            and message[2] == WALDORF_M
            and (message[4] == DUMP_SINGLE or message[4] == DUMP_MULTI))

def convertToProgramDump(channel, message, program_number):
    if isEditBufferDump(message) or isSingleProgramDump(message):
        bank = program_number // numberOfPatchesPerBank()
        program = program_number % numberOfPatchesPerBank()
        patchStoreWait()            # Wait between dumps for M to save to memory
        if bank == 0:
            new_message = copy(message)
            new_message[3] = 0x00
            new_message[4] = DUMP_MULTI
            new_message[32] = 0x01      # exact (0-1) if exact = 1 the M will save an arrangement dump into the slot, defined by next byte (slot)
            new_message[33] = program   # slot (0-127)
            new_message[34] = 0x00
            new_message[35] = 0x00
            return new_message        
        new_message = copy(message)
        new_message[3] = 0x00
        new_message[4] = DUMP_SINGLE    # if bank = 0 and sound = 0 – the M will save a dump into current active single sound
        new_message[32] = bank          # bank (1-16)
        new_message[33] = program       # program (0-127)
        new_message[34] = 0x00          # Setting this to 0 allows to save it in the synth
        new_message[35] = 0x00
        return new_message
    raise Exception("Can only convert program dumps")

#--------------------------------------------- FINGERPRINT

def calculateFingerprint(message):
    if isEditBufferDump(message) or isSingleProgramDump(message):
        data = copy(message)
        data[3] = 0x00                                                          # Blank out channel / deviceID
        data[nameBaseIndex:nameBaseIndex+nameLength] = [0] * nameLength         # Blank out program name
        data[32:35] = [0, 0]                                                    # Blank out program position and state
        return hashlib.md5(bytearray(data)).hexdigest()                         # Calculate the fingerprint from the cleaned data
    raise Exception("Can only fingerprint Presets")
    
#---------------------------------------------

# Test data picked up by test_adaptation.py
def make_test_data():
    def programs(data: testing.TestData) -> List[testing.ProgramTestData]:
        yield testing.ProgramTestData(message=data.all_messages[0], number=0, name="Wavetable El. Piano    ")

    def editbuffers(data: testing.TestData) -> List[testing.ProgramTestData]:
        yield testing.ProgramTestData(message=data.all_messages[0], number=0, name="Wavetable El. Piano    ")
        editBuffer = "F0 3E 30 00 72 01 20 59 6F 75 27 76 65 20 67 6F 74 20 69 74 21 20 20 20 20 20 20 20 20 20 20 00 00 00 00 00 00 40 00 40 7F 3F 02 40 00 40 0A 40 03 40 01 40 14 40 " \
                "03 40 0A 40 00 40 00 40 00 40 00 40 00 40 01 40 02 40 00 40 0A 40 03 40 01 40 14 40  04 40 0A 40 00 40 00 40 00 40 00 40 00 40 09 40 32 40  01 40 5D 3F 00 40 00 40 03 40 01 40 00 40 03 40 00 40  01 40 00 40 09 40 32 40 01 40 " \
                "5D 3F 00 40 00 40 03 40 01 40 00 40 03 40 00 40 01 40  00 40 00 40 40 40 40 40 00 40 00 40 00 40 00 40 00 40  00 40 00 40 00 40 00 40 00 40 22 40 00 40 39 40 14 40  00 40 3F 40 03 40 01 40 00 40 " \
                "04 40 05 40 03 40 00 40 5A 40 3F 40 00 40 00 40 03 40  01 40 00 40 03 40 00 40 00 40 03 40 00 40 36 40 5A 40  00 40 3C 40 19 40 00 40 18 40 00 40 1B 40 00 40 1A 40  00 40 01 40 02 40 06 40 41 40 " \
                "58 40 00 40 41 40 03 40 00 40 19 40 00 40 18 40 00 40  1B 40 00 40 1A 40 00 40 01 40 01 40 5F 40 7F 40 50 40  7F 40 7F 40 00 40 00 40 00 40 00 40 00 40 00 40 00 40  00 40 00 40 00 40 00 40 00 40 " \
                "00 40 00 40 00 40 00 40 00 40 00 40 06 40 00 40 00 40  00 40 00 40 00 40 7F 40 00 40 00 40 00 40 00 40 00 40  00 40 1E 40 00 40 00 40 00 40 19 40 00 40 1E 40 00 40  00 40 00 40 7F 40 00 40 0A 40 " \
                "00 40 00 40 00 40 00 40 00 40 00 40 20 40 01 40 00 40  01 40 00 40 00 40 28 40 00 40 00 40 00 40 00 40 00 40  00 40 00 40 00 40 00 40 00 40 00 40 00 40 00 40 00 40  00 40 00 40 00 40 00 40 00 40 " \
                "00 40 00 40 00 40 00 40 00 40 00 40 00 40 00 40 00 40  00 40 00 40 00 40 00 40 00 40 00 40 00 40 00 40 00 40  00 40 00 40 00 40 00 40 00 40 00 40 00 40 00 40 00 40  00 00 00 00 00 40 00 40 7F F7 "
        yield testing.ProgramTestData(message=editBuffer, number = 0, name = " You've got it!        ")
        program = "f0 3e 30 00 72 01 4a 6f 75 72 6e 65 79 20 74 6f 20 4d 20 56 53 20 20 20 20 20 20 20 20 20 20 00 00 00 00 00 00 40 00 40 00 40 04 40 00 40 0a 40 03 40 03 40 00 40 03 40 0b 40 00 40 00 40 00 40 01 40 00 40 04 40 04 40 00 40 0a 40 03 40 03 40 00 40 03 40 09 40 00 40 00 40 00 40 00 40 00 40 0c 40 00 40 01 40 2d 40 00 40 00 40 03 40 03 40 00 40 03 40 00 40 01 40 00 40 19 40 3a 40 01 40 6f 3f 00 40 00 40 03 40 03 40 00 40 03 40 00 40 00 40 00 40 00 40 40 40 40 40 00 40 00 40 00 40 00 40 00 40 00 40 00 40 00 40 00 40 00 40 48 40 00 40 03 40 02 40 2e 40 00 40 03 40 03 40 00 40 03 40 00 40 1a 40 7c 3f 38 40 12 40 3e 40 00 40 03 40 03 40 00 40 03 40 00 40 00 40 03 40 0b 40 1d 40 5d 40 68 40 46 40 03 40 00 40 00 40 00 40 03 40 00 40 03 40 00 40 01 40 10 40 00 40 1d 40 3d 40 0f 40 7f 40 03 40 00 40 03 40 00 40 03 40 00 40 03 40 00 40 03 40 00 40 01 40 01 40 1d 40 7f 40 45 40 00 40 46 40 7f 40 00 40 00 40 01 40 00 40 45 40 7f 40 45 40 00 40 00 40 00 40 00 40 00 40 00 40 00 40 02 40 01 40 00 40 06 40 00 40 00 40 00 40 00 40 00 40 7f 40 00 40 00 40 00 40 00 40 00 40 00 40 15 40 00 40 00 40 00 40 19 40 1e 40 06 40 00 40 01 40 00 40 7f 40 00 40 5f 40 00 40 3f 40 07 40 00 40 00 40 00 40 00 40 01 40 00 40 00 40 00 40 00 40 28 40 00 40 00 40 00 40 00 40 00 40 00 40 00 40 00 40 00 40 00 40 00 40 00 40 00 40 00 40 00 40 00 40 00 40 00 40 00 40 00 40 00 40 00 40 00 40 00 40 00 40 00 40 00 40 00 40 00 40 00 40 00 40 00 40 00 40 00 40 00 40 00 40 00 40 00 40 00 40 00 40 00 40 00 40 00 40 00 40 00 40 00 40 00 00 00 00 00 40 00 40 7f f7"
        yield testing.ProgramTestData(message=program, name="Journey to M VS        ")

    return testing.TestData(sysex="testData/Waldorf_M/Wavetable-El.-Piano.syx", program_generator=programs, edit_buffer_generator=editbuffers)
