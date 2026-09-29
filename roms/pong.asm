; pong.asm - single player pong against the right wall
;
; w (keypad 5) moves the paddle up, s (keypad 8) moves it down.
; bounce the ball off your paddle on the left, it rebounds off the
; right wall by itself. each paddle hit scores one point and beeps.
; miss the ball and the game ends; press 5 to serve again.
;
; V0 = ball x, V1 = ball y, V2 = dx (1 or 255), V3 = dy (1 or 255)
; V4 = paddle y, V5 = score, V6 = state (0 = playing, 1 = game over)
; built with: python3 tools/asm/main.py roms/pong.asm roms/pong.ch8

start:
    LD V4, 12        ; paddle y
    LD V5, 0         ; score
    LD V6, 0         ; playing
    LD V0, 32        ; ball x
    LD V1, 15        ; ball y
    LD V2, 1         ; moving right
    LD V3, 1         ; moving down

frame:
    CLS
    LD I, paddle     ; paddle: 2 wide, 8 tall at x = 2
    LD VA, 2
    DRW VA, V4, 8
    LD I, ball       ; ball: 2x2 pixels
    DRW V0, V1, 2

    LD VA, 5         ; paddle up
    SKP VA
    JP not_up
    LD VB, V4
    SE VB, 0
    ADD V4, 255
not_up:
    LD VA, 8         ; paddle down
    SKP VA
    JP not_down
    LD VB, V4
    SE VB, 24
    ADD V4, 1
not_down:

    LD VA, 8         ; frame pacing
    LD DT, VA
wait:
    LD VA, DT
    SE VA, 0
    JP wait

    SE V6, 1         ; game over? wait for 5 to restart
    JP playing
    LD VA, 5
    SKP VA
    JP frame
    JP start

playing:
    ADD V0, V2       ; move the ball
    ADD V1, V3

    SE V0, 62        ; right wall
    JP not_right
    LD V2, 255
    LD V0, 61
not_right:
    SE V0, 255       ; wrapped past the left edge: missed
    JP not_left
    LD V6, 1
    LD VA, 30
    LD ST, VA        ; sad beep
    JP frame
not_left:
    SE V1, 255       ; top wall
    JP not_top
    LD V3, 1
    LD V1, 0
not_top:
    SE V1, 31        ; bottom wall
    JP not_bottom
    LD V3, 255
    LD V1, 30
not_bottom:
    SE V0, 3         ; ball at the paddle's front, moving left?
    JP frame
    SE V2, 255
    JP frame
    LD VB, V4        ; y overlap: V1 <= V4 + 7 ...
    ADD VB, 7
    LD VC, VB
    SUB VC, V1
    SNE VF, 0
    JP frame
    LD VC, V1        ; ... and V1 + 1 >= V4
    ADD VC, 1
    SUB VC, V4
    SNE VF, 0
    JP frame
    LD V2, 1         ; bounce
    LD V0, 4
    ADD V5, 1        ; score
    LD VA, 10
    LD ST, VA        ; happy beep
    JP frame

paddle:
    DB 0xC0, 0xC0, 0xC0, 0xC0, 0xC0, 0xC0, 0xC0, 0xC0
ball:
    DB 0xC0, 0xC0
