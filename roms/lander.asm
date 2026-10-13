; lander.asm - lunar lander on a 64x32 screen
;
; keys: 5 thrust, 4 left, 6 right. land gently (slow vertical speed)
; on the lit pad to score, anything else is a crash. press 5 to fly again.
;
; VA = lander x, VB = lander y
; V2 = vy, signed (0..5 falling, 0xFB..0xFF rising)
; V3 = fuel, V4 = pad x, V5 = score, V7 = state (0 play, 1 won, 2 crash)
; built with: python3 tools/assemble.py roms/lander.asm roms/lander.ch8

start:
    RND V4, 63       ; pad x, snapped to 8px steps
    LD V6, 0x38
    AND V4, V6
    LD VA, 30
    LD VB, 0
    LD V2, 0
    LD V3, 40        ; fuel
    LD V5, 0         ; score
    LD V7, 0         ; playing

frame:
    CLS
    CALL draw_ground
    LD I, lander
    DRW VA, VB, 4

physics:
    LD V0, 5
    SKP V0           ; thrust?
    JP left
    LD V0, V3
    SNE V0, 0        ; out of fuel?
    JP left
    SE V2, 0xFB      ; clamp upward speed at -5
    JP burn
    JP left
burn:
    ADD V2, 254      ; vy -= 2
    ADD V3, 255      ; fuel -= 1

left:
    LD V0, 4
    SKP V0
    JP right
    ADD VA, 255
    SE VA, 255
    JP right
    LD VA, 0
right:
    LD V0, 6
    SKP V0
    JP gravity
    ADD VA, 1
    SE VA, 60
    JP gravity
    LD VA, 59

gravity:
    SNE V2, 5        ; cap fall speed at 5
    JP move
    ADD V2, 1

move:
    LD V0, V2
    LD V1, 0x80
    SUB V0, V1       ; VF=1 when vy is negative (rising)
    SE VF, 1
    JP fall
    LD V0, 0
    SUB V0, V2       ; V0 = -vy
    SUB VB, V0       ; climb
    LD V0, VB
    LD V1, 0x80
    SUB V0, V1       ; VF=1 when VB wrapped past the top
    SE VF, 1
    JP landed_check
    LD VB, 0
    JP landed_check
fall:
    ADD VB, V2

landed_check:
    LD V0, VB
    LD V1, 25        ; sprite is 4 tall, ground starts at row 29
    SUB V0, V1       ; VF=1 when VB >= 25 (touchdown)
    SE VF, 1
    JP wait_tick
    LD V0, V2
    LD V1, 3
    SUB V0, V1       ; VF=1 when vy >= 3, too fast to survive
    SE VF, 1
    JP check_pad
    JP crashed

check_pad:
    LD V0, VA
    ADD V0, 2        ; lander center x
    LD V1, V4
    SUB V0, V1       ; VF=1 when center >= pad x
    SE VF, 1
    JP crashed
    LD V1, 8
    SUB V1, V0       ; VF=1 when center < pad x + 8
    SE VF, 1
    JP crashed
    JP won

wait_tick:
    LD V0, 5         ; pacing
    LD DT, V0
tickwait:
    LD V0, DT
    SE V0, 0
    JP tickwait
    SE V7, 0
    JP over
    JP frame

won:
    LD V7, 1
    ADD V5, 1
    LD V0, 30
    LD ST, V0        ; beep
    JP over

crashed:
    LD V7, 2
    LD V0, 60
    LD ST, V0
    JP over

; end screen: ground, pad, lander or debris, wait for 5 to refly
over:
    CLS
    CALL draw_ground
    SE V7, 2
    JP over_lander
    LD I, boom
    DRW VA, VB, 7
    JP over_wait
over_lander:
    LD I, lander
    DRW VA, VB, 4
over_wait:
    LD V0, 5
    SKP V0
    JP over
    JP start

; draw ground rows 29-31, pad strip at row 28
draw_ground:
    LD V0, 0
    LD V1, 29
    LD I, ground
ground_col:
    DRW V0, V1, 3
    ADD V0, 8
    SE V0, 64
    JP ground_col
    LD V0, V4
    LD V1, 28
    LD I, pad
    DRW V0, V1, 1
    RET

ground:
    DB 0xFF, 0xFF, 0xFF
pad:
    DB 0xFF

lander:
    DB 0x20, 0x70, 0xF8, 0xA8

boom:
    DB 0x81, 0x42, 0x24, 0x18, 0x24, 0x42, 0x81
