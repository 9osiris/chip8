; invaders.asm - space invaders clone
;
; a row of 8 aliens marches side to side and drops down. you move
; the cannon with 4 and 6, fire with 5. aliens fire back randomly.
; VE = cannon x, V1 = bullet y (255 = inactive), V2 = alien bullet y,
; V3 = alien bullet x, V4 = march dir (1 right, 255 left),
; V5 = score, V6 = state (0 play, 1 win, 2 lose), V7 = march timer,
; V8 = alien x base, V9 = alien y base, VA = alien index temp
; built with: python3 tools/asm/main.py -o roms/invaders.ch8 roms/invaders.asm

start:
    LD V8, 8         ; alien base x
    LD V9, 4         ; alien base y
    LD V4, 1         ; march right
    LD VE, 28        ; cannon x
    LD V1, 255       ; player bullet off
    LD V2, 255       ; alien bullet off
    LD V5, 0         ; score
    LD V6, 0         ; playing
    LD V7, 0         ; march timer
    LD VC, 0         ; clear alien alive flags
inv_init:
    SNE VC, 8
    JP inv_init_done
    LD I, aliens
    ADD I, VC
    LD V0, 1
    LD [I], V0
    ADD VC, 1
    JP inv_init
inv_init_done:
    LD VE, 28

frame:
    CLS
    SNE V6, 0
    JP playing
    JP gameover

playing:
    LD VA, 4         ; cannon left
    SKP VA
    JP c_right
    SE VE, 2
    JP c_right
    ADD VE, 255
c_right:
    LD VA, 6
    SKP VA
    JP c_fire
    SE VE, 54
    JP c_fire
    ADD VE, 1
c_fire:
    LD VA, 5
    SKP VA
    JP bullet_upd
    SE V1, 255       ; fire only if no bullet
    JP bullet_upd
    LD V1, 26        ; bullet starts above cannon
bullet_upd:
    SE V1, 255
    JP b_move
    JP b_draw
b_move:
    ADD V1, 255      ; bullet rises
    SE V1, 6         ; reached alien row?
    JP b_draw
    CALL hit_alien
b_draw:
    SE V1, 255
    JP alien_upd
    LD I, shot
    LD VA, VE
    ADD VA, 3
    DRW VA, V1, 1

alien_upd:
    ADD V7, 1        ; march every 12 frames
    SE V7, 12
    JP a_bullet
    LD V7, 0
    SE V4, 1
    JP march_left
    SE V8, 40        ; at right edge?
    JP mr_move
    LD V4, 255       ; turn around
    ADD V9, 2
    JP a_bullet
mr_move:
    ADD V8, 2
    JP a_bullet
march_left:
    SE V8, 8         ; at left edge?
    JP ml_move
    LD V4, 1         ; turn around
    ADD V9, 2
    JP a_bullet
ml_move:
    ADD V8, 254
    JP a_bullet
a_bullet:
    SE V2, 255       ; alien bullet already flying?
    JP ab_move
    RND VA, 7        ; maybe fire
    SE VA, 0
    JP ab_draw
    RND VA, 7        ; pick a live alien column
    LD I, aliens
    ADD I, VA
    LD V0, [I]
    SE V0, 1
    JP ab_draw
    LD V3, VA        ; bullet x = alien x
    SHL V3
    SHL V3
    ADD V3, V8
    LD V2, V9        ; bullet y = alien y
    ADD V2, 4
ab_move:
    ADD V2, 1
    SE V2, 28        ; hit cannon row?
    JP ab_draw
    LD VB, VE        ; check cannon hit: |V3 - VE| < 8
    SUB VB, V3
    SE VF, 0
    JP ab_c1
    LD VB, V3
    SUB VB, VE
ab_c1:
    SE VB, 8
    JP ab_draw
    LD V6, 2         ; cannon destroyed
    JP draw_all
ab_draw:
    SE V2, 255
    JP draw_aliens
    LD I, shot
    DRW V3, V2, 1
    SE V2, 31
    JP draw_aliens
    LD V2, 255       ; bullet off bottom

draw_aliens:
    LD VC, 0
da_loop:
    SNE VC, 8
    JP draw_cannon
    LD I, aliens
    ADD I, VC
    LD V0, [I]
    SE V0, 1
    JP da_next
    LD VA, VC        ; alien x = V8 + VC * 8
    SHL VA
    SHL VA
    SHL VA
    ADD VA, V8
    LD I, alien
    DRW VA, V9, 3
da_next:
    ADD VC, 1
    JP da_loop

draw_cannon:
    LD I, cannon
    LD VB, 28
    DRW VE, VB, 2
draw_all:
    LD VA, 10        ; frame pacing
    LD DT, VA
wait:
    LD VA, DT
    SE VA, 0
    JP wait
    SE V9, 24        ; aliens reached the cannon?
    JP frame
    LD V6, 2
    JP frame

gameover:
    LD VA, 5
    SKP VA
    JP frame
    JP start

; check if player bullet (VE+3, V1) hit a live alien; uses VA, VB, VC
hit_alien:
    LD VC, 0
ha_loop:
    SNE VC, 8
    JP ha_miss
    LD I, aliens
    ADD I, VC
    LD V0, [I]
    SE V0, 1
    JP ha_next
    LD VA, VC        ; alien x
    SHL VA
    SHL VA
    SHL VA
    ADD VA, V8
    LD VB, VE        ; bullet x = cannon x + 3
    ADD VB, 3
    SUB VB, VA       ; dx = (VE+3) - alien_x
    SNE VF, 0
    JP ha_next       ; bullet left of alien
    LD VA, 7         ; dx <= 7?
    SUB VA, VB
    SNE VF, 0
    JP ha_next
    LD VB, V1        ; dy = V1 - V9
    SUB VB, V9
    SNE VF, 0
    JP ha_next
    LD VA, 3         ; dy <= 3?
    SUB VA, VB
    SNE VF, 0
    JP ha_next
    LD V0, 0         ; hit! clear alien
    LD I, aliens
    ADD I, VC
    LD [I], V0
    ADD V5, 1
    LD V1, 255       ; bullet gone
    LD VA, 8
    LD ST, VA
    SE V5, 8
    JP ha_done
    LD V6, 1         ; all dead, win
ha_done:
    RET
ha_next:
    ADD VC, 1
    JP ha_loop
ha_miss:
    RET

alien:
    DB 0x7E, 0xDB, 0x7E
cannon:
    DB 0x18, 0x3C
shot:
    DB 0x80
aliens:
    DB 0
