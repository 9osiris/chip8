; bounce.asm - a sprite bouncing around the 64x32 screen
;
; V0 = x, V1 = y, V2 = dx (1 or 255), V3 = dy (1 or 255)
; built with: python3 tools/assemble.py roms/bounce.asm roms/bounce.ch8

start:
    LD V0, 10
    LD V1, 12
    LD V2, 1
    LD V3, 1
    LD I, sprite

loop:
    CLS
    DRW V0, V1, 5

    LD V4, 12        ; frame pacing
    LD DT, V4
wait:
    LD V4, DT
    SE V4, 0
    JP wait

    ADD V0, V2       ; move x
    SE V0, 56        ; hit right edge?
    JP x_low
    LD V2, 255
    LD V0, 55
x_low:
    SE V0, 255       ; wrapped past left edge?
    JP move_y
    LD V2, 1
    LD V0, 0

move_y:
    ADD V1, V3       ; move y
    SE V1, 27        ; hit bottom edge?
    JP y_low
    LD V3, 255
    LD V1, 26
y_low:
    SE V1, 255       ; wrapped past top edge?
    JP loop
    LD V3, 1
    LD V1, 0
    JP loop

sprite:
    DB 0x3C, 0x7E, 0xFF, 0x7E, 0x3C
