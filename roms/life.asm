; life.asm - conway's game of life on a 32x16 torus
;
; watches a glider and a blinker evolve. press 0 for a random soup.
; each generation is drawn as 2x2 blocks, one cell per byte.
;
; gridA holds the current generation, gridB the next. the update
; reads the 8 neighbors with wraparound, applies the rules, then
; copies gridB back to gridA.
;
; VA = x (0-31), VB = y (0-15), VC = neighbor count
; VD = dy idx (0-2), VE = dx idx (0-2), V7 = state (0 run, 1 soup key latch)
; built with: python3 tools/asm/main.py -o roms/life.ch8 roms/life.asm

start:
    CALL clear_a
    LD I, initdata
    LD VD, 0         ; init index
init_copy:
    SNE VD, 8
    JP init_done
    LD I, initdata
    ADD I, VD
    LD V0, [I]       ; cell offset
    LD I, gridA
    ADD I, V0
    LD V0, 1
    LD [I], V0       ; gridA[offset] = 1
    ADD VD, 1
    JP init_copy
init_done:

frame:
    CLS
    CALL draw
    LD V0, 0         ; soup on key 0
    SKP V0
    JP no_soup
    SE V7, 1
    JP no_soup
    LD V7, 1
    CALL soup
    JP frame
no_soup:
    SKNP V0
    JP gen_wait
    LD V7, 0
gen_wait:
    LD V0, 30        ; pacing: one generation every 30 ticks
    LD DT, V0
wait:
    LD V0, DT
    SE V0, 0
    JP wait
    CALL gen
    JP frame

; zero out gridA (512 bytes)
clear_a:
    LD VE, 0         ; lo counter
    LD V7, 0         ; hi page
ca_loop:
    LD I, gridA
    SE V7, 0
    JP ca_no_hi
    LD I, gridA + 256
ca_no_hi:
    ADD I, VE
    LD V0, 0
    LD [I], V0
    ADD VE, 1
    SE VE, 0
    JP ca_loop
    ADD V7, 1
    SE V7, 2
    JP ca_loop
    LD V7, 0
    RET

; fill gridA with random live cells
soup:
    LD VE, 0
    LD VD, 0         ; hi page in VD this time
so_loop:
    LD I, gridA
    SE VD, 0
    JP so_no_hi
    LD I, gridA + 256
so_no_hi:
    ADD I, VE
    RND V0, 1
    LD [I], V0
    ADD VE, 1
    SE VE, 0
    JP so_loop
    ADD VD, 1
    SE VD, 2
    JP so_loop
    RET

; draw live cells as 2x2 blocks
draw:
    LD VE, 0         ; lo
    LD V7, 0         ; hi
dr_loop:
    LD I, gridA
    SE V7, 0
    JP dr_no_hi
    LD I, gridA + 256
dr_no_hi:
    ADD I, VE
    LD V0, [I]
    SE V0, 1
    JP dr_next
    LD V1, VE        ; x = (VE & 31) * 2
    LD V2, 31
    AND V1, V2
    SHL V1
    LD V2, VE        ; y = (V7 * 8 + (VE >> 5)) * 2
    SHR V2
    SHR V2
    SHR V2
    SHR V2
    SHR V2
    LD V3, V7
    SHL V3
    SHL V3
    SHL V3
    ADD V2, V3
    SHL V2
    LD I, block2
    DRW V1, V2, 2
dr_next:
    ADD VE, 1
    SE VE, 0
    JP dr_loop
    ADD V7, 1
    SE V7, 2
    JP dr_loop
    RET

; compute the next generation into gridB, then copy back
gen:
    LD VB, 0         ; y 0..15
gen_y:
    SNE VB, 16
    JP gen_done
    LD VA, 0         ; x 0..31
gen_x:
    SNE VA, 32
    JP gen_next_y
    CALL count_nb
    CALL read_a      ; V0 = current cell
    SE V0, 0
    JP was_alive
    SE VC, 3         ; dead: born if count == 3
    JP write_b0
    JP write_b1
was_alive:
    SE VC, 2         ; alive: survives on 2 or 3
    JP chk3
    JP write_b1
chk3:
    SE VC, 3
    JP write_b0
    JP write_b1
gen_next_x:
    ADD VA, 1
    JP gen_x
gen_next_y:
    ADD VB, 1
    JP gen_y
gen_done:
    CALL copy_ba
    RET

; count live neighbors of (VA, VB) into VC
count_nb:
    LD VC, 0
    LD VD, 0         ; dy idx
nb_dy:
    SNE VD, 3
    JP nb_done
    LD VE, 0         ; dx idx
nb_dx:
    SNE VE, 3
    JP nb_next_dy
    SE VE, 1         ; skip the center cell
    JP nb_do
    SE VD, 1
    JP nb_do
    JP nb_next_dx
nb_do:
    LD V0, VD        ; dy = VD - 1
    ADD V0, 255
    LD V1, VB
    ADD V1, V0
    LD V2, 15
    AND V1, V2       ; ny = (y + dy) & 15
    LD V0, VE        ; dx = VE - 1
    ADD V0, 255
    LD V2, VA
    ADD V2, V0
    LD V0, 31
    AND V2, V0       ; nx = (x + dx) & 31
    CALL read_nb     ; V0 = gridA[ny][nx]
    ADD VC, V0
nb_next_dx:
    ADD VE, 1
    JP nb_dx
nb_next_dy:
    ADD VD, 1
    JP nb_dy
nb_done:
    RET

; read gridA[VB][VA] into V0 (uses V1)
read_a:
    LD V1, VB
    SHL V1
    SHL V1
    SHL V1
    SHL V1           ; V1 = y * 16
    LD I, gridA
    ADD I, V1
    ADD I, V1        ; I = gridA + y * 32
    ADD I, VA
    LD V0, [I]
    RET

; read gridA[V1][V2] into V0 (ny in V1, nx in V2, uses V3)
read_nb:
    LD V3, V1
    SHL V3
    SHL V3
    SHL V3
    SHL V3           ; V3 = ny * 16
    LD I, gridA
    ADD I, V3
    ADD I, V3        ; I = gridA + ny * 32
    ADD I, V2
    LD V0, [I]
    RET

; write 0/1 to gridB[VB][VA] (uses V0, V1)
write_b0:
    LD V0, 0
    JP write_b
write_b1:
    LD V0, 1
write_b:
    LD V1, VB
    SHL V1
    SHL V1
    SHL V1
    SHL V1
    LD I, gridB
    ADD I, V1
    ADD I, V1
    ADD I, VA
    LD [I], V0
    JP gen_next_x

; copy gridB back to gridA
copy_ba:
    LD VE, 0
    LD V7, 0
cb_loop:
    LD I, gridB
    SE V7, 0
    JP cb_no_hi
    LD I, gridB + 256
cb_no_hi:
    ADD I, VE
    LD V0, [I]
    LD I, gridA
    SE V7, 0
    JP cb_no_hi2
    LD I, gridA + 256
cb_no_hi2:
    ADD I, VE
    LD [I], V0
    ADD VE, 1
    SE VE, 0
    JP cb_loop
    ADD V7, 1
    SE V7, 2
    JP cb_loop
    RET

; glider + blinker starting pattern (cell offsets = y * 32 + x)
initdata:
    DB 1, 34, 64, 65, 66, 170, 202, 234
block2:
    DB 0xC0, 0xC0
gridA:
    DB 0
    ORG gridA + 512
gridB:
    DB 0
