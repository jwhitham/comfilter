/* libSoX Biquad filter effects   (c) 2006-8 robs@users.sourceforge.net
 *
 * This library is free software; you can redistribute it and/or modify it
 * under the terms of the GNU Lesser General Public License as published by
 * the Free Software Foundation; either version 2.1 of the License, or (at
 * your option) any later version.
 *
 * This library is distributed in the hope that it will be useful, but
 * WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU Lesser
 * General Public License for more details.
 *
 * You should have received a copy of the GNU Lesser General Public License
 * along with this library; if not, write to the Free Software Foundation,
 * Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301  USA
 *
 *
 * 2-pole filters designed by Robert Bristow-Johnson <rbj@audioimagination.com>
 *   see https://webaudio.github.io/Audio-EQ-Cookbook/audio-eq-cookbook.html
 *
 * 1-pole filters based on code (c) 2000 Chris Bagwell <cbagwell@sprynet.com>
 *   Algorithms: Recursive single pole low/high pass filter
 *   Reference: The Scientist and Engineer's Guide to Digital Signal Processing
 *
 *   low-pass: output[N] = input[N] * A + output[N-1] * B
 *     X = exp(-2.0 * pi * Fc)
 *     A = 1 - X
 *     B = X
 *     Fc = cutoff freq / sample rate
 *
 *     Mimics an RC low-pass filter:
 *
 *     ---/\/\/\/\----------->
 *                   |
 *                  --- C
 *                  ---
 *                   |
 *                   |
 *                   V
 *
 *   high-pass: output[N] = A0 * input[N] + A1 * input[N-1] + B1 * output[N-1]
 *     X  = exp(-2.0 * pi * Fc)
 *     A0 = (1 + X) / 2
 *     A1 = -(1 + X) / 2
 *     B1 = X
 *     Fc = cutoff freq / sample rate
 *
 *     Mimics an RC high-pass filter:
 *
 *         || C
 *     ----||--------->
 *         ||    |
 *               <
 *               > R
 *               <
 *               |
 *               V
 */


#include "biquad.h"
#include <stdio.h>
#include <stdarg.h>
#include <stdlib.h>
#include <assert.h>
#include <string.h>
#include <math.h>
#include <limits.h>

#ifdef min
#undef min
#endif
#define min(a, b) ((a) <= (b) ? (a) : (b))

#ifdef max
#undef max
#endif
#define max(a, b) ((a) >= (b) ? (a) : (b))

#define dB_to_linear(x) exp((x) * M_LN10 * 0.05)
#define linear_to_dB(x) (log10(x) * 20)
#define sqr(a) ((a) * (a))

#define SOX_SAMPLE_MIN (INT_MIN)
#define SOX_SAMPLE_MAX (INT_MAX)
#define SOX_EFF_NULL     32          /**< Client API: Effect does nothing (can be optimized out of chain) */
#define SOX_ROUND_CLIP_COUNT(d, clips) \
  ((d) < 0? (d) <= SOX_SAMPLE_MIN - 0.5? ++(clips), SOX_SAMPLE_MIN: (d) - 0.5 \
        : (d) >= SOX_SAMPLE_MAX + 0.5? ++(clips), SOX_SAMPLE_MAX: (d) + 0.5)

typedef biquad_t priv_t;

static void lsx_fail(const char* error, ...) {
    va_list ap;
    va_start(ap, error);
    vfprintf(stderr, error, ap);
    va_end(ap);
    fprintf(stderr, "\n");
}

static int lsx_biquad_start2(sox_effect_t * effp)
{
  priv_t * p = (priv_t *)effp->priv;

  /* Simplify: */
  p->b2 /= p->a0;
  p->b1 /= p->a0;
  p->b0 /= p->a0;
  p->a2 /= p->a0;
  p->a1 /= p->a0;

  p->o2 = p->o1 = p->i2 = p->i1 = 0;

  return SOX_SUCCESS;
}


int lsx_biquad_flow(sox_effect_t * effp, const sox_sample_t *ibuf,
    sox_sample_t *obuf, size_t *isamp, size_t *osamp)
{
  priv_t * p = (priv_t *)effp->priv;
  size_t len = *isamp = *osamp = min(*isamp, *osamp);
  while (len--) {
    double o0 = *ibuf*p->b0 + p->i1*p->b1 + p->i2*p->b2 - p->o1*p->a1 - p->o2*p->a2;
    p->i2 = p->i1, p->i1 = *ibuf++;
    p->o2 = p->o1, p->o1 = o0;
    *obuf++ = SOX_ROUND_CLIP_COUNT(o0, effp->clips);
  }
  return SOX_SUCCESS;
}


int lsx_biquad_start(sox_effect_t * effp, double fc, double width)
{
  double w0, alpha, mult;
  priv_t * p = calloc(1, sizeof(biquad_t));

  if (!p) {
    lsx_fail("allocating biquad_t");
    return SOX_EOF;
  }

  effp->priv = p;

  p->fc = fc;   // frequency, Hz
  p->width = width;  // width, Hz
  p->width_type = width_bw_Hz; // width type is Hz
  p->filter_type = filter_BPF; 

  w0 = 2 * M_PI * p->fc / effp->in_signal.rate;
  alpha = 0, mult = dB_to_linear(max(p->gain, 0));

  if (w0 > M_PI) {
    lsx_fail("frequency must be less than half the sample-rate (Nyquist rate)");
    return SOX_EOF;
  }

  /* Set defaults: */
  p->b0 = p->b1 = p->b2 = p->a1 = p->a2 = 0;
  p->a0 = 1;

  {
      alpha = sin(w0)/(2*p->fc/p->width);
  }
  {
      p->b0 =   alpha;
      p->b1 =   0;
      p->b2 =  -alpha;
      p->a0 =   1 + alpha;
      p->a1 =  -2*cos(w0);
      p->a2 =   1 - alpha;
  }
  if (effp->in_signal.mult)
    *effp->in_signal.mult /= mult;
  return lsx_biquad_start2(effp);
}
