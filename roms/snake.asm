; snake.asm - classic snake on a 16x8 grid of 4x4 cells
;
; 2/8/4/6 steer up/down/left/right (numpad style). eat the flashing
; food to grow and score. walls and your own tail end the game;
; press 5 to play again.
;
; VA = head x cell (0-15), VB = head y cell (0-7)
; V2 = dir (0 right, 1 down, 2 left, 3 up)
; V3 = food x, V4 = food y, V5 = score, V6 = length, V7 = state
; body segments live at segs as packed bytes (y * 16 + x)
; built with: python3 tools/asm/main.py -o roms/snake.ch8 roms/snake.asm

start:
    LD VA, 8         ; head starts at (8, 4)
    LD VB, 4
    LD V2, 0         ; moving right
    LD V5, 0         ; score
    LD V6, 3         ; length
    LD V7, 0         ; playing
    LD I, segs       ; body: (8,4) (7,4) (6,4)
    LD V0, 0x48
    LD [I], V0
    LD I, segs + 1
    LD V0, 0x47
    LD [I], V0
    LD I, segs + 2
    LD V0, 0x46
    LD [I], V0
    CALL place_food

frame:
    CLS
    CALL draw
    CALL input
    LD V0, 8         ; one move every 8 ticks
    LD DT, V0
wait:
    LD V0, DT
    SE V0, 0
    JP wait
    SE V7, 1         ; dead? wait for 5 to restart
    JP alive
    LD V0, 5
    SKP V0
    JP frame
    JP start
alive:
    CALL move
    JP frame

; read the steering keys, ignore 180 degree turns
input:
    LD V0, 2
    SKP V0
    JP in_not_up
    SNE V2, 1
    JP in_not_up
    LD V2, 3
in_not_up:
    LD V0, 8
    SKP V0
    JP in_not_down
    SNE V2, 3
    JP in_not_down
    LD V2, 1
in_not_down:
    LD V0, 4
    SKP V0
    JP in_not_left
    SNE V2, 0
    JP in_not_left
    LD V2, 2
in_not_left:
    LD V0, 6
    SKP V0
    JP in_not_right
    SNE V2, 2
    JP in_not_right
    LD V2, 0
in_not_right:
    RET

; draw food and every body segment as 4x4 blocks
draw:
    LD I, block
    LD V0, V3
    SHL V0
    SHL V0           ; food x * 4
    LD VC, V4
    SHL VC
    SHL VC           ; food y * 4
    DRW V0, VC, 4
    LD VE, 0         ; segment index
seg_loop:
    SNE VE, V6
    JP seg_done
    LD I, segs
    ADD I, VE
    LD V0, [I]       ; packed cell byte
    LD VD, 15
    LD VC, V0
    AND VC, VD       ; x = byte & 15
    SHL VC
    SHL VC           ; x * 4
    LD VD, V0
    SHR VD
    SHR VD
    SHR VD
    SHR VD           ; y = byte >> 4
    SHL VD
    SHL VD           ; y * 4
    LD I, block
    DRW VC, VD, 4
    ADD VE, 1
    JP seg_loop
seg_done:
    RET

; advance the snake one cell
move:
    SE V2, 0
    JP m_not_r
    ADD VA, 1
m_not_r:
    SE V2, 1
    JP m_not_d
    ADD VB, 1
m_not_d:
    SE V2, 2
    JP m_not_l
    ADD VA, 255
m_not_l:
    SE V2, 3
    JP m_not_u
    ADD VB, 255
m_not_u:
    LD V0, 15        ; wall check: VA <= 15 and VB <= 7
    SUB V0, VA
    SE VF, 1
    JP dead
    LD V0, 7
    SUB V0, VB
    SE VF, 1
    JP dead
    LD VE, 0         ; ate flag
    SE VA, V3        ; new head on the food?
    JP m_no_eat
    SE VB, V4
    JP m_no_eat
    ADD V6, 1        ; grow
    ADD V5, 1        ; score
    LD V0, 20
    LD ST, V0        ; happy beep
    LD VE, 1
m_no_eat:
    LD V1, VB        ; pack the new head byte
    SHL V1
    SHL V1
    SHL V1
    SHL V1
    ADD V1, VA
    LD VC, V6        ; shift the body down one slot
    ADD VC, 255
m_shift:
    SNE VC, 0
    JP m_shift_done
    LD VD, VC
    ADD VD, 255
    LD I, segs
    ADD I, VD
    LD V0, [I]
    LD I, segs
    ADD I, VC
    LD [I], V0
    ADD VC, 255
    JP m_shift
m_shift_done:
    LD VC, 1         ; hit ourselves? check seg[1]..seg[V6-1]
m_coll:
    SNE VC, V6
    JP m_coll_done
    LD I, segs
    ADD I, VC
    LD V0, [I]
    SE V0, V1
    JP m_coll_next
    JP dead
m_coll_next:
    ADD VC, 1
    JP m_coll
m_coll_done:
    LD I, segs       ; store the new head
    LD V0, V1
    LD [I], V0
    SE VE, 1         ; ate? drop new food
    JP m_done
    CALL place_food
m_done:
    RET

dead:
    LD V7, 1
    LD V0, 30
    LD ST, V0        ; sad beep
    RET

; pick a food cell that is not on the snake
place_food:
    RND V3, 15
    RND V4, 7
    LD VC, 0
pf_loop:
    SNE VC, V6
    JP pf_ok
    LD I, segs
    ADD I, VC
    LD V0, [I]
    LD VD, V4
    SHL VD
    SHL VD
    SHL VD
    SHL VD
    ADD VD, V3       ; packed candidate
    SE V0, VD
    JP pf_next
    JP place_food    ; occupied, try again
pf_next:
    ADD VC, 1
    JP pf_loop
pf_ok:
    RET

block:
    DB 0xF0, 0xF0, 0xF0, 0xF0
segs:
    DB 0
