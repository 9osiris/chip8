; catch.asm - catch the falling pixel with your paddle
;
; keys: keypad 4 moves left, keypad 6 moves right (q and r on a keyboard)
; V0 = pixel x, V1 = pixel y, V6 = paddle x, V7 = score
; built with: python3 tools/assemble.py roms/catch.asm roms/catch.ch8

start:
    LD V6, 28
    LD V7, 0
    LD V8, 29        ; paddle row
    LD I, player

newpixel:
    RND V0, 63       ; random column
    LD V1, 0

frame:
    CLS
    DRW V6, V8, 5    ; paddle
    LD I, pixel
    DRW V0, V1, 1    ; falling pixel
    LD I, player

    LD VA, 4
    SKP VA           ; left key?
    JP right
    ADD V6, 255
    SE V6, 255       ; clamped at 0
    JP right
    LD V6, 0
right:
    LD VA, 6
    SKP VA           ; right key?
    JP moved
    ADD V6, 1
    SE V6, 57        ; clamped at 56
    JP moved
    LD V6, 56

moved:
    ADD V1, 1        ; pixel falls one row

    LD VB, 10        ; pacing
    LD DT, VB
wait:
    LD VB, DT
    SE VB, 0
    JP wait

    SE V1, 29        ; pixel at paddle row?
    JP miss
    LD VD, V0
    SUB VD, V6       ; VF=1 if pixel x >= paddle x
    SNE VF, 0
    JP miss
    LD VE, VD
    LD VC, 8
    SUB VE, VC       ; VF=0 (borrow) if overlap is under 8 wide
    SE VF, 0
    JP miss

caught:
    ADD V7, 1        ; score++
    LD VB, 30
    LD ST, VB        ; beep
    JP newpixel

miss:
    SE V1, 31        ; fell past the paddle?
    JP frame
    JP newpixel

player:
    DB 0x3C, 0x7E, 0xFF, 0x7E, 0x3C
pixel:
    DB 0x80
