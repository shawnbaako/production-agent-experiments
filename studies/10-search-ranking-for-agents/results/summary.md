# Replica results (test split)

| Arm | n | NDCG@5 | NDCG@10 | MRR | Recall@5 |
|---|---|---|---|---|---|
| Pool order (no query) | 96 | 0.289 | 0.394 | 0.294 | 0.159 |
| BM25 | 96 | 0.515 | 0.574 | 0.559 | 0.385 |
| Nomic v1.5 cosine | 96 | 0.538 | 0.595 | 0.580 | 0.414 |
| EmbeddingGemma 2 cosine | 96 | 0.747 | 0.783 | 0.803 | 0.595 |
| EmbeddingGemma 2, no query prefix | 96 | 0.727 | 0.771 | 0.821 | 0.564 |
| EmbeddingGemma 2, 256 dimensions | 96 | 0.730 | 0.768 | 0.805 | 0.583 |
| bge-reranker-v2-m3 | 96 | 0.739 | 0.772 | 0.805 | 0.613 |
| Jev noul | 96 | 0.911 | 0.919 | 0.983 | 0.760 |

## NDCG@10 per language

| Lang | n | pool | bm25 | nomic | eg2 | eg2_noprefix | eg2_256 | bge | jev |
|---|---|---|---|---|---|---|---|---|---|
| en | 24 | 0.394 | 0.696 | 0.736 | 0.810 | 0.780 | 0.801 | 0.778 | 0.932 |
| es | 6 | 0.377 | 0.730 | 0.623 | 0.789 | 0.770 | 0.783 | 0.934 | 0.959 |
| zh | 8 | 0.484 | 0.535 | 0.321 | 0.750 | 0.756 | 0.732 | 0.674 | 0.916 |
| de | 6 | 0.513 | 0.669 | 0.699 | 0.801 | 0.727 | 0.742 | 0.695 | 0.932 |
| fr | 8 | 0.374 | 0.570 | 0.586 | 0.766 | 0.773 | 0.745 | 0.754 | 0.887 |
| ja | 7 | 0.355 | 0.355 | 0.447 | 0.744 | 0.750 | 0.682 | 0.749 | 0.913 |
| pt | 9 | 0.311 | 0.691 | 0.618 | 0.796 | 0.780 | 0.795 | 0.730 | 0.885 |
| ko | 9 | 0.415 | 0.415 | 0.484 | 0.807 | 0.788 | 0.830 | 0.816 | 0.961 |
| it | 7 | 0.380 | 0.611 | 0.742 | 0.849 | 0.821 | 0.838 | 0.786 | 0.936 |
| ar | 6 | 0.364 | 0.364 | 0.524 | 0.749 | 0.743 | 0.734 | 0.748 | 0.926 |
| hi | 6 | 0.383 | 0.383 | 0.477 | 0.660 | 0.749 | 0.651 | 0.842 | 0.834 |
| non_en | 72 | 0.394 | 0.534 | 0.548 | 0.774 | 0.768 | 0.757 | 0.769 | 0.915 |

## NDCG@10 per query kind

| Kind | n | pool | bm25 | nomic | eg2 | eg2_noprefix | eg2_256 | bge | jev |
|---|---|---|---|---|---|---|---|---|---|
| precise | 36 | 0.237 | 0.552 | 0.577 | 0.833 | 0.806 | 0.828 | 0.800 | 0.922 |
| vague | 28 | 0.475 | 0.536 | 0.594 | 0.737 | 0.704 | 0.707 | 0.706 | 0.922 |
| negation | 24 | 0.489 | 0.624 | 0.522 | 0.729 | 0.748 | 0.716 | 0.791 | 0.932 |
| nomatch | 8 | 0.533 | 0.660 | 0.894 | 0.878 | 0.914 | 0.871 | 0.818 | 0.858 |

## Paired differences, 95% CI (cluster bootstrap over English source queries)

- jev-bge:ndcg10: +0.148 [+0.080, +0.218]
- jev-bge:ndcg5: +0.172 [+0.095, +0.251]
- jev-bge:ndcg10:en: +0.153 [+0.081, +0.234]
- jev-bge:ndcg10:es: +0.024 [-0.063, +0.092]
- jev-bge:ndcg10:zh: +0.242 [+0.120, +0.370]
- jev-bge:ndcg10:de: +0.237 [+0.077, +0.401]
- jev-bge:ndcg10:fr: +0.133 [+0.057, +0.216]
- jev-bge:ndcg10:ja: +0.164 [+0.001, +0.354]
- jev-bge:ndcg10:pt: +0.155 [-0.008, +0.342]
- jev-bge:ndcg10:ko: +0.145 [+0.052, +0.283]
- jev-bge:ndcg10:it: +0.150 [+0.085, +0.212]
- jev-bge:ndcg10:ar: +0.178 [+0.073, +0.298]
- jev-bge:ndcg10:hi: -0.009 [-0.235, +0.198]
- jev-bge:ndcg10:non_en: +0.146 [+0.078, +0.219]
- jev-bm25:ndcg10: +0.345 [+0.266, +0.431]
- jev-bm25:ndcg5: +0.396 [+0.307, +0.489]
- jev-bm25:ndcg10:en: +0.236 [+0.140, +0.344]
- jev-bm25:ndcg10:es: +0.229 [+0.013, +0.458]
- jev-bm25:ndcg10:zh: +0.381 [+0.210, +0.561]
- jev-bm25:ndcg10:de: +0.263 [+0.055, +0.487]
- jev-bm25:ndcg10:fr: +0.317 [+0.138, +0.510]
- jev-bm25:ndcg10:ja: +0.559 [+0.377, +0.734]
- jev-bm25:ndcg10:pt: +0.194 [+0.035, +0.372]
- jev-bm25:ndcg10:ko: +0.546 [+0.424, +0.655]
- jev-bm25:ndcg10:it: +0.324 [+0.153, +0.516]
- jev-bm25:ndcg10:ar: +0.563 [+0.408, +0.745]
- jev-bm25:ndcg10:hi: +0.451 [+0.175, +0.738]
- jev-bm25:ndcg10:non_en: +0.381 [+0.297, +0.469]
- jev-eg2:ndcg10: +0.137 [+0.066, +0.214]
- jev-eg2:ndcg5: +0.165 [+0.076, +0.262]
- jev-eg2:ndcg10:en: +0.122 [+0.056, +0.201]
- jev-eg2:ndcg10:es: +0.169 [+0.043, +0.308]
- jev-eg2:ndcg10:zh: +0.166 [+0.064, +0.274]
- jev-eg2:ndcg10:de: +0.131 [+0.040, +0.229]
- jev-eg2:ndcg10:fr: +0.121 [+0.016, +0.230]
- jev-eg2:ndcg10:ja: +0.170 [-0.002, +0.395]
- jev-eg2:ndcg10:pt: +0.089 [-0.078, +0.290]
- jev-eg2:ndcg10:ko: +0.154 [+0.043, +0.290]
- jev-eg2:ndcg10:it: +0.086 [+0.010, +0.194]
- jev-eg2:ndcg10:ar: +0.177 [+0.029, +0.358]
- jev-eg2:ndcg10:hi: +0.174 [-0.037, +0.402]
- jev-eg2:ndcg10:non_en: +0.141 [+0.068, +0.221]
- bge-bm25:ndcg10: +0.197 [+0.117, +0.285]
- bge-bm25:ndcg5: +0.224 [+0.132, +0.321]
- bge-bm25:ndcg10:en: +0.082 [-0.010, +0.191]
- bge-bm25:ndcg10:es: +0.204 [+0.013, +0.422]
- bge-bm25:ndcg10:zh: +0.139 [-0.076, +0.389]
- bge-bm25:ndcg10:de: +0.025 [-0.229, +0.308]
- bge-bm25:ndcg10:fr: +0.184 [-0.007, +0.382]
- bge-bm25:ndcg10:ja: +0.395 [+0.240, +0.535]
- bge-bm25:ndcg10:pt: +0.039 [-0.039, +0.113]
- bge-bm25:ndcg10:ko: +0.401 [+0.273, +0.529]
- bge-bm25:ndcg10:it: +0.175 [-0.001, +0.348]
- bge-bm25:ndcg10:ar: +0.385 [+0.235, +0.607]
- bge-bm25:ndcg10:hi: +0.459 [+0.215, +0.719]
- bge-bm25:ndcg10:non_en: +0.236 [+0.146, +0.325]
- bge-eg2:ndcg10: -0.011 [-0.058, +0.043]
- bge-eg2:ndcg5: -0.007 [-0.068, +0.064]
- bge-eg2:ndcg10:en: -0.032 [-0.096, +0.027]
- bge-eg2:ndcg10:es: +0.145 [+0.032, +0.264]
- bge-eg2:ndcg10:zh: -0.076 [-0.217, +0.061]
- bge-eg2:ndcg10:de: -0.107 [-0.215, -0.013]
- bge-eg2:ndcg10:fr: -0.012 [-0.078, +0.053]
- bge-eg2:ndcg10:ja: +0.006 [-0.142, +0.170]
- bge-eg2:ndcg10:pt: -0.065 [-0.122, -0.010]
- bge-eg2:ndcg10:ko: +0.009 [-0.043, +0.079]
- bge-eg2:ndcg10:it: -0.063 [-0.137, +0.021]
- bge-eg2:ndcg10:ar: -0.001 [-0.060, +0.083]
- bge-eg2:ndcg10:hi: +0.182 [-0.043, +0.420]
- bge-eg2:ndcg10:non_en: -0.004 [-0.053, +0.051]
- eg2-nomic:ndcg10: +0.188 [+0.122, +0.257]
- eg2-nomic:ndcg5: +0.208 [+0.131, +0.284]
- eg2-nomic:ndcg10:en: +0.074 [+0.029, +0.121]
- eg2-nomic:ndcg10:es: +0.166 [-0.043, +0.405]
- eg2-nomic:ndcg10:zh: +0.430 [+0.235, +0.622]
- eg2-nomic:ndcg10:de: +0.103 [-0.001, +0.220]
- eg2-nomic:ndcg10:fr: +0.180 [+0.080, +0.329]
- eg2-nomic:ndcg10:ja: +0.297 [+0.068, +0.547]
- eg2-nomic:ndcg10:pt: +0.178 [+0.082, +0.285]
- eg2-nomic:ndcg10:ko: +0.324 [+0.033, +0.594]
- eg2-nomic:ndcg10:it: +0.107 [-0.073, +0.313]
- eg2-nomic:ndcg10:ar: +0.225 [+0.067, +0.364]
- eg2-nomic:ndcg10:hi: +0.183 [-0.030, +0.459]
- eg2-nomic:ndcg10:non_en: +0.226 [+0.140, +0.311]
- eg2-bm25:ndcg10: +0.208 [+0.117, +0.302]
- eg2-bm25:ndcg5: +0.231 [+0.126, +0.340]
- eg2-bm25:ndcg10:en: +0.114 [+0.025, +0.216]
- eg2-bm25:ndcg10:es: +0.059 [-0.213, +0.331]
- eg2-bm25:ndcg10:zh: +0.215 [-0.037, +0.479]
- eg2-bm25:ndcg10:de: +0.132 [-0.047, +0.341]
- eg2-bm25:ndcg10:fr: +0.196 [-0.033, +0.417]
- eg2-bm25:ndcg10:ja: +0.389 [+0.173, +0.600]
- eg2-bm25:ndcg10:pt: +0.104 [+0.013, +0.193]
- eg2-bm25:ndcg10:ko: +0.392 [+0.273, +0.517]
- eg2-bm25:ndcg10:it: +0.238 [+0.081, +0.405]
- eg2-bm25:ndcg10:ar: +0.386 [+0.166, +0.643]
- eg2-bm25:ndcg10:hi: +0.277 [-0.094, +0.650]
- eg2-bm25:ndcg10:non_en: +0.240 [+0.142, +0.345]
- eg2_noprefix-eg2:ndcg10: -0.012 [-0.040, +0.014]
- eg2_noprefix-eg2:ndcg5: -0.020 [-0.055, +0.011]
- eg2_noprefix-eg2:ndcg10:en: -0.030 [-0.061, -0.003]
- eg2_noprefix-eg2:ndcg10:es: -0.020 [-0.096, +0.035]
- eg2_noprefix-eg2:ndcg10:zh: +0.005 [-0.050, +0.063]
- eg2_noprefix-eg2:ndcg10:de: -0.074 [-0.137, -0.015]
- eg2_noprefix-eg2:ndcg10:fr: +0.007 [-0.053, +0.067]
- eg2_noprefix-eg2:ndcg10:ja: +0.006 [-0.032, +0.043]
- eg2_noprefix-eg2:ndcg10:pt: -0.016 [-0.043, +0.005]
- eg2_noprefix-eg2:ndcg10:ko: -0.019 [-0.082, +0.024]
- eg2_noprefix-eg2:ndcg10:it: -0.028 [-0.074, +0.008]
- eg2_noprefix-eg2:ndcg10:ar: -0.006 [-0.101, +0.089]
- eg2_noprefix-eg2:ndcg10:hi: +0.089 [+0.007, +0.210]
- eg2_noprefix-eg2:ndcg10:non_en: -0.006 [-0.036, +0.021]
- eg2_256-eg2:ndcg10: -0.014 [-0.031, +0.004]
- eg2_256-eg2:ndcg5: -0.017 [-0.039, +0.006]
- eg2_256-eg2:ndcg10:en: -0.009 [-0.023, +0.005]
- eg2_256-eg2:ndcg10:es: -0.006 [-0.065, +0.053]
- eg2_256-eg2:ndcg10:zh: -0.018 [-0.052, +0.014]
- eg2_256-eg2:ndcg10:de: -0.060 [-0.084, -0.032]
- eg2_256-eg2:ndcg10:fr: -0.021 [-0.053, +0.015]
- eg2_256-eg2:ndcg10:ja: -0.062 [-0.107, -0.024]
- eg2_256-eg2:ndcg10:pt: -0.001 [-0.043, +0.035]
- eg2_256-eg2:ndcg10:ko: +0.023 [-0.026, +0.101]
- eg2_256-eg2:ndcg10:it: -0.011 [-0.044, +0.022]
- eg2_256-eg2:ndcg10:ar: -0.016 [-0.080, +0.043]
- eg2_256-eg2:ndcg10:hi: -0.009 [-0.035, +0.024]
- eg2_256-eg2:ndcg10:non_en: -0.016 [-0.035, +0.005]

## Other results

```json
{
 "searches": {
  "all": 240,
  "test": 192,
  "test_ranked": 96,
  "test_nomatch": 96,
  "nomatch_by_kind": {
   "vague": 12,
   "negation": 16,
   "nomatch": 32,
   "precise": 36
  },
  "ranked_by_kind": {
   "precise": 36,
   "vague": 28,
   "negation": 24,
   "nomatch": 8
  },
  "relevant_per_ranked_search_mean": 5.25,
  "grade_counts": {
   "0": 1184,
   "2": 114,
   "1": 371,
   "3": 61
  }
 },
 "nomatch": {
  "bge": {
   "said_none_when_none": [
    96,
    96
   ],
   "said_none_when_some": [
    78,
    96
   ],
   "top_score_nomatch_p50": 0.0009,
   "top_score_match_p50": 0.0299,
   "said_none_by_best_grade": {
    "2": [
     35,
     40
    ],
    "3": [
     43,
     56
    ]
   }
  },
  "jev": {
   "said_none_when_none": [
    94,
    96
   ],
   "said_none_when_some": [
    24,
    96
   ],
   "top_score_nomatch_p50": 0.03,
   "top_score_match_p50": 0.705,
   "said_none_by_best_grade": {
    "2": [
     20,
     40
    ],
    "3": [
     4,
     56
    ]
   }
  }
 },
 "floors": {
  "nomic": {
   "production": 0.6,
   "dev_youden": 0.56,
   "production_result": {
    "relevant_cleared": [
     86,
     504
    ],
    "grade0_cleared_share": 0.0304,
    "nomatch_nothing_cleared": [
     80,
     96
    ],
    "match_nothing_cleared": [
     57,
     96
    ],
    "relevant_cleared_by_lang": {
     "en": [
      58,
      126
     ],
     "es": [
      1,
      19
     ],
     "zh": [
      0,
      36
     ],
     "de": [
      2,
      49
     ],
     "fr": [
      7,
      50
     ],
     "ja": [
      0,
      56
     ],
     "pt": [
      14,
      44
     ],
     "ko": [
      0,
      53
     ],
     "it": [
      4,
      26
     ],
     "ar": [
      0,
      26
     ],
     "hi": [
      0,
      19
     ]
    }
   },
   "dev_youden_result": {
    "relevant_cleared": [
     156,
     504
    ],
    "grade0_cleared_share": 0.0842,
    "nomatch_nothing_cleared": [
     64,
     96
    ],
    "match_nothing_cleared": [
     44,
     96
    ],
    "relevant_cleared_by_lang": {
     "en": [
      88,
      126
     ],
     "es": [
      4,
      19
     ],
     "zh": [
      0,
      36
     ],
     "de": [
      9,
      49
     ],
     "fr": [
      21,
      50
     ],
     "ja": [
      0,
      56
     ],
     "pt": [
      24,
      44
     ],
     "ko": [
      0,
      53
     ],
     "it": [
      9,
      26
     ],
     "ar": [
      0,
      26
     ],
     "hi": [
      1,
      19
     ]
    }
   },
   "recall30": {
    "en": 0.6783,
    "all": 0.4766,
    "fr": 0.5383,
    "non_en": 0.4094,
    "ja": 0.0587,
    "pt": 0.7074,
    "zh": 0.179,
    "de": 0.4727,
    "es": 0.4821,
    "hi": 0.3571,
    "ko": 0.1765,
    "it": 0.6905,
    "ar": 0.4444
   }
  },
  "eg2": {
   "production": 0.665,
   "dev_youden": 0.64,
   "production_result": {
    "relevant_cleared": [
     270,
     504
    ],
    "grade0_cleared_share": 0.0704,
    "nomatch_nothing_cleared": [
     74,
     96
    ],
    "match_nothing_cleared": [
     23,
     96
    ],
    "relevant_cleared_by_lang": {
     "en": [
      77,
      126
     ],
     "es": [
      10,
      19
     ],
     "zh": [
      16,
      36
     ],
     "de": [
      24,
      49
     ],
     "fr": [
      29,
      50
     ],
     "ja": [
      34,
      56
     ],
     "pt": [
      26,
      44
     ],
     "ko": [
      26,
      53
     ],
     "it": [
      11,
      26
     ],
     "ar": [
      11,
      26
     ],
     "hi": [
      6,
      19
     ]
    }
   },
   "dev_youden_result": {
    "relevant_cleared": [
     342,
     504
    ],
    "grade0_cleared_share": 0.1466,
    "nomatch_nothing_cleared": [
     46,
     96
    ],
    "match_nothing_cleared": [
     16,
     96
    ],
    "relevant_cleared_by_lang": {
     "en": [
      92,
      126
     ],
     "es": [
      12,
      19
     ],
     "zh": [
      22,
      36
     ],
     "de": [
      32,
      49
     ],
     "fr": [
      34,
      50
     ],
     "ja": [
      45,
      56
     ],
     "pt": [
      32,
      44
     ],
     "ko": [
      34,
      53
     ],
     "it": [
      15,
      26
     ],
     "ar": [
      13,
      26
     ],
     "hi": [
      11,
      19
     ]
    }
   },
   "recall30": {
    "en": 0.8016,
    "all": 0.7842,
    "fr": 0.6858,
    "non_en": 0.7785,
    "ja": 0.8714,
    "pt": 0.9494,
    "zh": 0.7273,
    "de": 0.6132,
    "es": 0.8155,
    "hi": 0.631,
    "ko": 0.8444,
    "it": 0.8333,
    "ar": 0.7183
   }
  },
  "eg2_noprefix": {
   "production": 0.61,
   "dev_youden": 0.62,
   "production_result": {
    "relevant_cleared": [
     292,
     504
    ],
    "grade0_cleared_share": 0.1188,
    "nomatch_nothing_cleared": [
     59,
     96
    ],
    "match_nothing_cleared": [
     17,
     96
    ],
    "relevant_cleared_by_lang": {
     "en": [
      75,
      126
     ],
     "es": [
      11,
      19
     ],
     "zh": [
      22,
      36
     ],
     "de": [
      22,
      49
     ],
     "fr": [
      23,
      50
     ],
     "ja": [
      36,
      56
     ],
     "pt": [
      31,
      44
     ],
     "ko": [
      34,
      53
     ],
     "it": [
      13,
      26
     ],
     "ar": [
      13,
      26
     ],
     "hi": [
      12,
      19
     ]
    }
   },
   "dev_youden_result": {
    "relevant_cleared": [
     257,
     504
    ],
    "grade0_cleared_share": 0.0876,
    "nomatch_nothing_cleared": [
     67,
     96
    ],
    "match_nothing_cleared": [
     17,
     96
    ],
    "relevant_cleared_by_lang": {
     "en": [
      69,
      126
     ],
     "es": [
      11,
      19
     ],
     "zh": [
      20,
      36
     ],
     "de": [
      17,
      49
     ],
     "fr": [
      17,
      50
     ],
     "ja": [
      29,
      56
     ],
     "pt": [
      30,
      44
     ],
     "ko": [
      32,
      53
     ],
     "it": [
      13,
      26
     ],
     "ar": [
      8,
      26
     ],
     "hi": [
      11,
      19
     ]
    }
   },
   "recall30": {
    "en": 0.7804,
    "all": 0.7766,
    "fr": 0.7162,
    "non_en": 0.7753,
    "ja": 0.8429,
    "pt": 0.9111,
    "zh": 0.7585,
    "de": 0.62,
    "es": 0.881,
    "hi": 0.6071,
    "ko": 0.7926,
    "it": 0.8571,
    "ar": 0.6905
   }
  },
  "eg2_256": {
   "production": 0.71,
   "dev_youden": 0.66,
   "production_result": {
    "relevant_cleared": [
     164,
     504
    ],
    "grade0_cleared_share": 0.0434,
    "nomatch_nothing_cleared": [
     85,
     96
    ],
    "match_nothing_cleared": [
     31,
     96
    ],
    "relevant_cleared_by_lang": {
     "en": [
      59,
      126
     ],
     "es": [
      7,
      19
     ],
     "zh": [
      9,
      36
     ],
     "de": [
      5,
      49
     ],
     "fr": [
      13,
      50
     ],
     "ja": [
      15,
      56
     ],
     "pt": [
      22,
      44
     ],
     "ko": [
      21,
      53
     ],
     "it": [
      4,
      26
     ],
     "ar": [
      7,
      26
     ],
     "hi": [
      2,
      19
     ]
    }
   },
   "dev_youden_result": {
    "relevant_cleared": [
     341,
     504
    ],
    "grade0_cleared_share": 0.172,
    "nomatch_nothing_cleared": [
     48,
     96
    ],
    "match_nothing_cleared": [
     14,
     96
    ],
    "relevant_cleared_by_lang": {
     "en": [
      95,
      126
     ],
     "es": [
      12,
      19
     ],
     "zh": [
      21,
      36
     ],
     "de": [
      27,
      49
     ],
     "fr": [
      33,
      50
     ],
     "ja": [
      42,
      56
     ],
     "pt": [
      35,
      44
     ],
     "ko": [
      35,
      53
     ],
     "it": [
      17,
      26
     ],
     "ar": [
      14,
      26
     ],
     "hi": [
      10,
      19
     ]
    }
   },
   "recall30": {
    "en": 0.7676,
    "all": 0.7574,
    "fr": 0.6809,
    "non_en": 0.754,
    "ja": 0.8349,
    "pt": 0.916,
    "zh": 0.6847,
    "de": 0.5984,
    "es": 0.7143,
    "hi": 0.631,
    "ko": 0.8111,
    "it": 0.8571,
    "ar": 0.7183
   }
  }
 },
 "latency": {
  "bge": {
   "p50": 0.3119,
   "p95": 0.4833,
   "device": "NVIDIA GeForce RTX 3080 Ti"
  },
  "jev": {
   "p50": 0.252,
   "p95": 0.315,
   "usd_per_search": 0.000195,
   "input_tokens_mean": 4632,
   "served_models": {
    "typesafe/jev-1.14-20261014": 240
   },
   "providers": {
    "TypeSafe": 240
   },
   "searches": 240
  },
  "jev_rerun": {
   "p50": 0.259,
   "p95": 0.328,
   "usd_per_search": 0.000194,
   "input_tokens_mean": 4630,
   "served_models": {
    "typesafe/jev-1.14-20261014": 192
   },
   "providers": {
    "TypeSafe": 192
   },
   "searches": 192
  },
  "embed": {
   "nomic_docs": 0.722,
   "nomic_queries": 0.197,
   "eg2_docs": 1.708,
   "eg2_queries": 0.216,
   "eg2_raw_queries": 0.2,
   "device": "NVIDIA GeForce RTX 3080 Ti"
  }
 },
 "jev_drift": {
  "searches": 192,
  "scores": 5536,
  "threshold_flips": 20,
  "max_abs_delta": 0.1,
  "mean_abs_delta": 0.0045,
  "same_order": 23,
  "same_top1": 166,
  "ndcg10_rerun": 0.9175,
  "ndcg10_change_mean": -0.0018,
  "ndcg10_change_max_abs": 0.1377,
  "nomatch_verdict_changed": 5,
  "rerun_said_none_when_none": [
   95,
   96
  ],
  "rerun_said_none_when_some": [
   24,
   96
  ]
 },
 "injection": {
  "shared": {
   "honest_repeat": {
    "injected_max_gain": 0.01,
    "injected_mean_gain": -0.0,
    "injected_crossed_0.5_upward": 0,
    "others_min_delta": -0.04,
    "others_max_abs_delta": 0.05,
    "others_crossed_0.5_downward": 0
   },
   "injected": {
    "injected_max_gain": 0.07,
    "injected_mean_gain": -0.006,
    "injected_crossed_0.5_upward": 0,
    "others_min_delta": -0.22,
    "others_max_abs_delta": 0.22,
    "others_crossed_0.5_downward": 1
   },
   "unicode": {
    "injected_max_gain": 0.06,
    "injected_mean_gain": -0.006,
    "injected_crossed_0.5_upward": 0,
    "others_min_delta": -0.14,
    "others_max_abs_delta": 0.14,
    "others_crossed_0.5_downward": 0
   },
   "honest_injected_listing_scores_max": 0.96
  },
  "isolated": {
   "honest_repeat": {
    "injected_max_gain": 0.02,
    "injected_mean_gain": -0.003,
    "injected_crossed_0.5_upward": 0,
    "others_min_delta": -0.06,
    "others_max_abs_delta": 0.07,
    "others_crossed_0.5_downward": 0
   },
   "injected": {
    "injected_max_gain": 0.04,
    "injected_mean_gain": -0.012,
    "injected_crossed_0.5_upward": 0,
    "others_min_delta": -0.07,
    "others_max_abs_delta": 0.1,
    "others_crossed_0.5_downward": 0
   },
   "unicode": {
    "injected_max_gain": 0.04,
    "injected_mean_gain": -0.002,
    "injected_crossed_0.5_upward": 0,
    "others_min_delta": -0.06,
    "others_max_abs_delta": 0.19,
    "others_crossed_0.5_downward": 0
   },
   "honest_injected_listing_scores_max": 0.98
  }
 },
 "spotcheck": {
  "pairs": 43,
  "exact": 31,
  "within_one": 42,
  "same_side_of_2": 38,
  "judge_higher": 12,
  "judge_lower": 0
 },
 "spend_usd": {
  "label": 0.0382,
  "jev": 0.0486,
  "jev_rerun": 0.0373,
  "inject": 0.0191,
  "total": 0.1433
 }
}
```
