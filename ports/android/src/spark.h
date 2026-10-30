/* The sparks off a car scraping a wall: the arcade's clCarSparkManager (one a car, under its
 * clCarEffectManager), run each arcade frame and drawn additive after the scene. */
#ifndef SPARK_H
#define SPARK_H

#include "car.h"
#include "mathx.h"
#include "render.h"

#define SPARK_CARS (1 + CAR_RIVALS) /* the player's, then the rivals' */

/* none flying (a new race) */
void spark_reset(void);
/* One arcade frame of car k's sparks: new ones while e says it scrapes (e NULL: the car is
 * off the road, its sparks go), then all of them fly on; body is its model matrix (they keep
 * to its position) */
void spark_step(int k, const float *body, const car_effect *e);
/* Draw them all, as the lights (render_begin in effect) */
void spark_draw(const mat4 *proj, const mat4 *view, render_params *rp);

#endif
