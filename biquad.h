/* libSoX Biquad filter common definitions (c) 2006-7 robs@users.sourceforge.net
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
 */

#ifndef biquad_included
#define biquad_included

#include <stdint.h>
#include <stddef.h>

typedef int32_t sox_int32_t;
typedef uint64_t sox_uint64_t;
typedef sox_int32_t sox_sample_t;
typedef double sox_rate_t;
typedef struct sox_signalinfo_t {
  sox_rate_t       rate;         /**< samples per second, 0 if unknown */
  unsigned         channels;     /**< number of sound channels, 0 if unknown */
  unsigned         precision;    /**< bits per sample, 0 if unknown */
  sox_uint64_t     length;       /**< samples * chans in file, 0 if unknown, -1 if unspecified */
  double           * mult;       /**< Effects headroom multiplier; may be null */
} sox_signalinfo_t;
typedef struct sox_effect_t sox_effect_t;
struct sox_effect_t {
//  sox_effects_globals_t    * global_info; /**< global effect parameters */
  sox_signalinfo_t         in_signal;     /**< Information about the incoming data stream */
//  sox_signalinfo_t         out_signal;    /**< Information about the outgoing data stream */
//  sox_encodinginfo_t       const * in_encoding;  /**< Information about the incoming data encoding */
//  sox_encodinginfo_t       const * out_encoding; /**< Information about the outgoing data encoding */
//  sox_effect_handler_t     handler;   /**< The handler for this effect */
    sox_uint64_t         clips;         /**< increment if clipping occurs */
//  size_t               flows;         /**< 1 if MCHAN, number of chans otherwise */
//  size_t               flow;          /**< flow number */
    void                 * priv;        /**< Effect's private data area (each flow has a separate copy) */
//  /* The following items are private to the libSoX effects chain functions. */
//  sox_sample_t             * obuf;    /**< output buffer */
//  size_t                   obeg;      /**< output buffer: start of valid data section */
//  size_t                   oend;      /**< output buffer: one past valid data section (oend-obeg is length of current content) */
//  size_t               imin;          /**< minimum input buffer content required for calling this effect's flow function; set via lsx_effect_set_imin() */
};
enum sox_error_t {
  SOX_SUCCESS = 0,     /**< Function succeeded = 0 */
  SOX_EOF = -1,        /**< End Of File or other error = -1 */
  SOX_EHDR = 2000,     /**< Invalid Audio Header = 2000 */
  SOX_EFMT,            /**< Unsupported data format = 2001 */
  SOX_ENOMEM,          /**< Can't alloc memory = 2002 */
  SOX_EPERM,           /**< Operation not permitted = 2003 */
  SOX_ENOTSUP,         /**< Operation not supported = 2004 */
  SOX_EINVAL           /**< Invalid argument = 2005 */
};




#define LSX_EFF_ALIAS

typedef enum {
  filter_LPF,
  filter_HPF,
  filter_BPF_CSG,
  filter_BPF,
  filter_notch,
  filter_APF,
  filter_peakingEQ,
  filter_lowShelf,
  filter_highShelf,
  filter_LPF_1,
  filter_HPF_1,
  filter_BPF_SPK,
  filter_BPF_SPK_N,
  filter_AP1,
  filter_AP2,
  filter_deemph,
  filter_riaa
} filter_t;

typedef enum {
  width_bw_Hz,
  width_bw_kHz,
  /* The old, non-RBJ, non-freq-warped band-pass/reject response;
   * leaving here for now just in case anybody misses it: */
  width_bw_old,
  width_bw_oct,
  width_Q,
  width_slope
} width_t;

/* Private data for the biquad filter effects */
typedef struct {
  double gain;             /* For EQ filters */
  double fc;               /* Centre/corner/cutoff frequency */
  double width;            /* Filter width; interpreted as per width_type */
  width_t width_type;

  filter_t filter_type;

  double b0, b1, b2;       /* Filter coefficients */
  double a0, a1, a2;       /* Filter coefficients */

  sox_sample_t i1, i2;     /* Filter memory */
  double      o1, o2;      /* Filter memory */
} biquad_t;

int lsx_biquad_start(sox_effect_t * effp, double fc, double width);
int lsx_biquad_flow(sox_effect_t * effp, const sox_sample_t *ibuf, sox_sample_t *obuf,
                        size_t *isamp, size_t *osamp);

#endif
