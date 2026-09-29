; breakout.asm - break all 40 bricks with a bouncing ball
;
; q (keypad 4) and r (keypad 6) move the paddle. keep the ball up,
; each brick scores one point. clear them all to win, drop the ball
; to lose. press 5 to play again.
;
; V0 = ball x, V1 = ball y, V2 = dx (1 or 255), V3 = dy (1 or 255)
; V4 = paddle x, V5 = score, V6 = state (0 play, 1 win, 2 lose)
; bricks live at bricks: 8 cols x 5 rows of 1 = alive
; built with: python3 tools/asm/main.py -o roms/breakout.ch8 roms/breakout.asm

start:
    LD VC, 0         ; fill the brick field
init:
    SNE VC, 40
    JP init_done
    LD I, bricks
    ADD I, VC
    LD V0, 1
    LD [I], V0
    ADD VC, 1
    JP init
init_done:
    LD V8, 28        ; paddle y
    LD V4, 27        ; paddle x
    LD V5, 0         ; score
    LD V6, 0         ; playing
    LD V0, 32        ; ball
    LD V1, 20
    LD V2, 1         ; right
    LD V3, 255       ; up

frame:
    CLS
    LD V7, V0        ; draw_bricks clobbers V0
    CALL draw_bricks
    LD V0, V7
    LD I, paddle     ; paddle 10x2
    DRW V4, V8, 2
    LD I, ball       ; ball 2x2
    DRW V0, V1, 2

    LD VA, 4         ; paddle left
    SKP VA
    JP not_left
    LD VB, V4
    SE VB, 0
    ADD V4, 255
not_left:
    LD VA, 6         ; paddle right
    SKP VA
    JP not_right
    LD VB, V4
    SE VB, 54
    ADD V4, 1
not_right:

    LD VA, 6         ; frame pacing
    LD DT, VA
wait:
    LD VA, DT
    SE VA, 0
    JP wait

    SNE V6, 0        ; over? wait for 5 to restart
    JP playing
    LD VA, 5
    SKP VA
    JP frame
    JP start

playing:
    ADD V0, V2       ; move the ball
    ADD V1, V3

    SE V0, 62        ; right wall
    JP not_rwall
    LD V2, 255
    LD V0, 61
not_rwall:
    SE V0, 255       ; left wall
    JP not_lwall
    LD V2, 1
    LD V0, 0
not_lwall:
    SE V1, 255       ; ceiling
    JP not_ceil
    LD V3, 1
    LD V1, 0
not_ceil:

    CALL brick_hit

    SE V3, 1         ; paddle check, only when falling
    JP after_paddle
    SE V1, 28
    JP after_paddle
    LD VA, V4        ; x overlap: V0 <= V4 + 9 ...
    ADD VA, 9
    SUB VA, V0
    SNE VF, 0
    JP after_paddle
    LD VA, V0        ; ... and V0 + 1 >= V4
    ADD VA, 1
    SUB VA, V4
    SNE VF, 0
    JP after_paddle
    LD V3, 255       ; bounce up
    LD V1, 26
    LD VA, 10
    LD ST, VA
after_paddle:
    SE V3, 1         ; fell past the paddle?
    JP frame
    SE V1, 30
    JP frame
    LD V6, 2         ; lose
    LD VA, 30
    LD ST, VA
    JP frame

; draw every live brick
draw_bricks:
    LD VC, 0
db_loop:
    SNE VC, 40
    JP db_done
    LD I, bricks
    ADD I, VC
    LD V0, [I]
    SE V0, 1
    JP db_next
    LD VD, VC
    LD VE, 7
    AND VD, VE       ; col = idx & 7
    SHL VD
    SHL VD
    SHL VD           ; x = col * 8
    LD VE, VC
    SHR VE
    SHR VE
    SHR VE           ; row = idx >> 3
    SHL VE
    SHL VE
    ADD VE, 2        ; y = 2 + row * 4
    LD I, brick
    DRW VD, VE, 3
db_next:
    ADD VC, 1
    JP db_loop
db_done:
    RET

; bounce off a brick if the ball is touching one
brick_hit:
    LD V7, V0        ; save ball x
    LD VB, V7
    SHR VB
    SHR VB
    SHR VB           ; col = x >> 3
    LD VC, V1
    ADD VC, 254      ; V1 - 2
    SHR VC
    SHR VC           ; row = (V1 - 2) >> 2
    LD VD, 4
    SUB VD, VC       ; need row <= 4
    SE VF, 1
    JP bh_miss
    LD VD, VC
    SHL VD
    SHL VD
    SHL VD           ; row * 8
    ADD VD, VB       ; idx = row * 8 + col
    LD I, bricks
    ADD I, VD
    LD V0, [I]
    SE V0, 1
    JP bh_miss
    LD VE, VC        ; brick_top = 2 + row * 4
    SHL VE
    SHL VE
    ADD VE, 2
    LD V0, VE        ; y overlap: V1 <= brick_top + 2 ...
    ADD V0, 2
    SUB V0, V1
    SE VF, 1
    JP bh_miss
    LD V0, V1        ; ... and V1 + 1 >= brick_top
    ADD V0, 1
    SUB V0, VE
    SE VF, 1
    JP bh_miss
    LD I, bricks     ; hit: clear it
    ADD I, VD
    LD V0, 0
    LD [I], V0
    ADD V5, 1
    LD V0, 10
    LD ST, V0
    SE V3, 1
    JP bh_was_up
    LD V3, 255
    JP bh_dy_done
bh_was_up:
    LD V3, 1
bh_dy_done:
    LD V0, V7
    SE V5, 40        ; all gone? win
    JP bh_done
    LD V6, 1
    JP bh_done
bh_miss:
    LD V0, V7        ; restore ball x
bh_done:
    RET

paddle:
    DB 0xFF, 0xC0, 0xFF, 0xC0
ball:
    DB 0xC0, 0xC0
brick:
    DB 0xFF, 0xFF, 0xFF
bricks:
    DB 0
