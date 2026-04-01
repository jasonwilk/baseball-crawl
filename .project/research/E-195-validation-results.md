# E-195 Plays Pipeline Validation Results

Automated comparison of plays-derived FPS and QAB counts
against GC season-stats API values.

## Plays Data Coverage

- **Completed games**: 101
- **Games with plays data**: 101 (100.0%)
- **Games without plays data**: 0

## FPS (First Pitch Strike) Comparison

**Overall match rate**: 55.6%
(15 of 27 pitchers within 5.0% tolerance)

| Player | Team | Derived | GC | Diff | % Diff | Status |
|--------|------|---------|----|------|--------|--------|
| Austin Rodocker | Lincoln Rebels 14U | 106 | 101 | 5 | 5.0% | OK |
| Beckett Meens | Lincoln Rebels 14U | 134 | 151 | 17 | 11.3% | MISMATCH |
| Brody Henninger | Standing Bear Freshman Grizzlies | 21 | 26 | 5 | 19.2% | MISMATCH |
| Caiden Strauss | Standing Bear Freshman Grizzlies | 6 | 7 | 1 | 14.3% | MISMATCH |
| Chase Lightner | Lincoln Rebels 14U | 206 | 212 | 6 | 2.8% | OK |
| Cole Silvertrust | Standing Bear Freshman Grizzlies | 4 | 4 | 0 | 0.0% | OK |
| Easton Larkins | Standing Bear Freshman Grizzlies | 1 | 1 | 0 | 0.0% | OK |
| Evan Mittan-DeBuhr | Lincoln Rebels 14U | 58 | 58 | 0 | 0.0% | OK |
| Grant Oliver | Standing Bear Freshman Grizzlies | 7 | 6 | 1 | 16.7% | MISMATCH |
| Hudson Reimers | Lincoln Rebels 14U | 99 | 119 | 20 | 16.8% | MISMATCH |
| Jace Stanczyk | Standing Bear Freshman Grizzlies | 20 | 21 | 1 | 4.8% | OK |
| James Powell | Standing Bear Freshman Grizzlies | 2 | 2 | 0 | 0.0% | OK |
| Kadyn Lichtenberg | Lincoln Rebels 14U | 113 | 124 | 11 | 8.9% | MISMATCH |
| Kadyn Lichtenberg | Standing Bear Freshman Grizzlies | 3 | 3 | 0 | 0.0% | OK |
| Keenan Treat | Lincoln Rebels 14U | 45 | 48 | 3 | 6.2% | MISMATCH |
| Kyler Hoffman | Standing Bear Freshman Grizzlies | 1 | 1 | 0 | 0.0% | OK |
| Levin Nguyen | Standing Bear Freshman Grizzlies | 6 | 6 | 0 | 0.0% | OK |
| Liam Beiermann | Standing Bear Freshman Grizzlies | 18 | 18 | 0 | 0.0% | OK |
| Oliver Hitz | Lincoln Rebels 14U | 59 | 48 | 11 | 22.9% | MISMATCH |
| Owen Hemmingsen | Lincoln Rebels 14U | 117 | 117 | 0 | 0.0% | OK |
| Owen Robison | Standing Bear Freshman Grizzlies | 4 | 4 | 0 | 0.0% | OK |
| Owen Rodocker | Lincoln Rebels 14U | 199 | 189 | 10 | 5.3% | MISMATCH |
| Reid Wilkinson | Lincoln Rebels 14U | 84 | 90 | 6 | 6.7% | MISMATCH |
| Reid Wilkinson | Standing Bear Freshman Grizzlies | 0 | 0 | 0 | 0.0% | OK |
| Tanner Rahmatulla | Standing Bear Freshman Grizzlies | 10 | 12 | 2 | 16.7% | MISMATCH |
| Thomas Saddler | Standing Bear Freshman Grizzlies | 22 | 20 | 2 | 10.0% | MISMATCH |
| Truman Jackson | Lincoln Rebels 14U | 104 | 103 | 1 | 1.0% | OK |

### FPS Discrepancy Diagnostics

#### Beckett Meens (Lincoln Rebels 14U)
Derived=134, GC=151, Diff=17 (11.3%)

**Per-game breakdown:**

| Game | Date | PAs | FPS Count |
|------|------|-----|-----------|
| `9014514d-b923-4536-8b30-72029dd059a8` | 2025-04-05 | 14 | 5 |
| `69ca1ed9-f933-407b-937f-d710f4d81c2d` | 2025-04-08 | 7 | 7 |
| `4c91cd0b-33d4-463d-a9a4-181bc42aec9c` | 2025-04-13 | 13 | 8 |
| `717fd9ea-7dac-478a-bcb9-0e83cf315e67` | 2025-04-20 | 11 | 6 |
| `453df5f6-24d2-4ba9-a788-90647f0f4dd3` | 2025-04-26 | 16 | 7 |
| `adfddd15-0633-4963-abbe-d7d3d8b1448b` | 2025-05-03 | 8 | 6 |
| `24fccda9-110e-4614-be8b-3cc821ba8527` | 2025-05-09 | 13 | 5 |
| `3badec1a-f9dc-4912-8f57-5b668fa2d8e6` | 2025-05-10 | 6 | 3 |
| `7914a47d-f7cd-4e96-b5fc-b9dbae7175dc` | 2025-05-17 | 5 | 2 |
| `7b3c3f89-c5da-4a0b-8040-3709f07d25c3` | 2025-05-18 | 4 | 2 |
| `703e594d-049d-495c-98f1-d56b9699b5e2` | 2025-05-24 | 16 | 12 |
| `e1ae3e43-74c4-4a4d-a978-75ce82550af7` | 2025-05-30 | 20 | 11 |
| `4f368d04-ee78-4400-b8e8-45ae48b8b345` | 2025-06-01 | 5 | 4 |
| `e0b95549-522c-4df5-9c47-108854c59f0e` | 2025-06-07 | 3 | 1 |
| `5db6c410-2e37-4c5b-a83e-929b75d36998` | 2025-06-13 | 27 | 18 |
| `3b945477-27d6-41cd-ad0c-c4599f036f07` | 2025-06-14 | 9 | 8 |
| `6bfac025-58e1-432b-9eb6-906b92324a91` | 2025-06-14 | 19 | 14 |
| `34c07055-2653-4baa-9b68-9a451fd97052` | 2025-06-21 | 3 | 2 |
| `870581ed-725c-4d31-99ca-2eabbad1101e` | 2025-06-27 | 8 | 6 |
| `6a5260f1-569f-4adf-9876-b3f951ce2aef` | 2025-07-07 | 5 | 5 |
| `bd1f8d2c-fc33-4dfb-b936-f960567c9502` | 2025-07-07 | 4 | 2 |

**Sample plays:**

| Game | Order | Inn | Half | Outcome | Pitches | FPS |
|------|-------|-----|------|---------|---------|-----|
| `24fccda9-110e-4614-be8b-3cc821ba8527` | 0 | 1 | top | Strikeout | 3 | 1 |
| `24fccda9-110e-4614-be8b-3cc821ba8527` | 1 | 1 | top | Line Out | 2 | 0 |
| `24fccda9-110e-4614-be8b-3cc821ba8527` | 2 | 1 | top | Walk | 6 | 1 |
| `24fccda9-110e-4614-be8b-3cc821ba8527` | 3 | 1 | top | Fly Out | 2 | 0 |
| `24fccda9-110e-4614-be8b-3cc821ba8527` | 15 | 2 | top | Error | 5 | 0 |

#### Brody Henninger (Standing Bear Freshman Grizzlies)
Derived=21, GC=26, Diff=5 (19.2%)

**Per-game breakdown:**

| Game | Date | PAs | FPS Count |
|------|------|-----|-----------|
| `91d00308-a64a-4738-bb7a-7f5be266e1c1` | 2026-03-19 | 10 | 6 |
| `374ca73f-342c-4f24-a5ca-af155e09e9d9` | 2026-03-25 | 3 | 3 |
| `903c7d39-ea42-4669-a621-9756be5fd8b1` | 2026-03-28 | 11 | 6 |
| `2975658b-9608-4176-a3df-69aa45d00af3` | 2026-04-01 | 6 | 6 |

**Sample plays:**

| Game | Order | Inn | Half | Outcome | Pitches | FPS |
|------|-------|-----|------|---------|---------|-----|
| `2975658b-9608-4176-a3df-69aa45d00af3` | 58 | 6 | top | Strikeout | 6 | 1 |
| `2975658b-9608-4176-a3df-69aa45d00af3` | 59 | 6 | top | Strikeout | 4 | 1 |
| `2975658b-9608-4176-a3df-69aa45d00af3` | 60 | 6 | top | Fly Out | 3 | 1 |
| `2975658b-9608-4176-a3df-69aa45d00af3` | 64 | 7 | top | Strikeout | 5 | 1 |
| `2975658b-9608-4176-a3df-69aa45d00af3` | 65 | 7 | top | Strikeout | 3 | 1 |

#### Caiden Strauss (Standing Bear Freshman Grizzlies)
Derived=6, GC=7, Diff=1 (14.3%)

**Per-game breakdown:**

| Game | Date | PAs | FPS Count |
|------|------|-----|-----------|
| `91d00308-a64a-4738-bb7a-7f5be266e1c1` | 2026-03-19 | 5 | 4 |
| `757c024c-de8d-4b44-b159-7704a6ff0640` | 2026-03-21 | 6 | 2 |

**Sample plays:**

| Game | Order | Inn | Half | Outcome | Pitches | FPS |
|------|-------|-----|------|---------|---------|-----|
| `757c024c-de8d-4b44-b159-7704a6ff0640` | 36 | 3 | top | Fly Out | 4 | 1 |
| `757c024c-de8d-4b44-b159-7704a6ff0640` | 42 | 4 | top | Walk | 6 | 0 |
| `757c024c-de8d-4b44-b159-7704a6ff0640` | 43 | 4 | top | Strikeout | 5 | 0 |
| `757c024c-de8d-4b44-b159-7704a6ff0640` | 44 | 4 | top | Single | 2 | 0 |
| `757c024c-de8d-4b44-b159-7704a6ff0640` | 45 | 4 | top | Strikeout | 3 | 1 |

#### Grant Oliver (Standing Bear Freshman Grizzlies)
Derived=7, GC=6, Diff=1 (16.7%)

**Per-game breakdown:**

| Game | Date | PAs | FPS Count |
|------|------|-----|-----------|
| `155bc5ef-3347-4b23-b4ed-4ea8f1e3e9c7` | 2026-03-20 | 6 | 3 |
| `757c024c-de8d-4b44-b159-7704a6ff0640` | 2026-03-21 | 6 | 3 |
| `a31f3884-456d-484b-a5c8-8df3333e3de7` | 2026-03-26 | 3 | 1 |

**Sample plays:**

| Game | Order | Inn | Half | Outcome | Pitches | FPS |
|------|-------|-----|------|---------|---------|-----|
| `155bc5ef-3347-4b23-b4ed-4ea8f1e3e9c7` | 13 | 2 | top | Walk | 4 | 0 |
| `155bc5ef-3347-4b23-b4ed-4ea8f1e3e9c7` | 14 | 2 | top | Single | 4 | 1 |
| `155bc5ef-3347-4b23-b4ed-4ea8f1e3e9c7` | 15 | 2 | top | Fly Out | 2 | 0 |
| `155bc5ef-3347-4b23-b4ed-4ea8f1e3e9c7` | 16 | 2 | top | Walk | 4 | 0 |
| `155bc5ef-3347-4b23-b4ed-4ea8f1e3e9c7` | 17 | 2 | top | Single | 4 | 1 |

#### Hudson Reimers (Lincoln Rebels 14U)
Derived=99, GC=119, Diff=20 (16.8%)

**Per-game breakdown:**

| Game | Date | PAs | FPS Count |
|------|------|-----|-----------|
| `990ea59c-ef58-44f9-9da0-7980c1c66bdf` | 2025-04-02 | 12 | 4 |
| `d48ba0c2-4231-4fd6-830a-41e0ea1e32c3` | 2025-04-05 | 2 | 1 |
| `c37ddf68-ac19-43c9-b694-27e837713415` | 2025-04-13 | 18 | 11 |
| `3dcb2a12-7957-4b3f-9061-687069d0770b` | 2025-04-23 | 6 | 3 |
| `06715ac5-4d35-4c96-a945-d9593f63c68f` | 2025-04-28 | 4 | 4 |
| `adfddd15-0633-4963-abbe-d7d3d8b1448b` | 2025-05-03 | 6 | 3 |
| `e2e6f43f-8671-4f0e-909d-f1642a7fc127` | 2025-05-04 | 10 | 7 |
| `107b43c3-b3b2-406f-8f51-74ad25d5c913` | 2025-05-10 | 13 | 8 |
| `87a88e9b-c744-4c98-8f2b-1da5e2183340` | 2025-05-11 | 1 | 0 |
| `077a027a-f296-4784-9f94-a325f8b646dd` | 2025-05-17 | 21 | 8 |
| `601a7a79-f536-4058-bdfc-02b148347501` | 2025-05-21 | 9 | 6 |
| `4ffe4f10-3379-4e50-978f-e4e1ba78cde4` | 2025-05-24 | 8 | 5 |
| `27325678-5b01-4a13-8254-93a4fdf71cad` | 2025-05-29 | 12 | 5 |
| `40716575-284a-40f5-8de0-a7317ffd9913` | 2025-06-08 | 13 | 8 |
| `a6b45809-0b67-41eb-ac20-f03ffbdc1f1c` | 2025-06-13 | 5 | 2 |
| `49d13d90-3831-41cb-8def-da0162a77e67` | 2025-06-27 | 7 | 4 |
| `6a5260f1-569f-4adf-9876-b3f951ce2aef` | 2025-07-07 | 12 | 7 |
| `bd1f8d2c-fc33-4dfb-b936-f960567c9502` | 2025-07-07 | 3 | 2 |
| `86199e44-b708-4778-9b89-6e91d74ab9c8` | 2025-07-12 | 13 | 9 |
| `1e0f8dfc-a7cb-46ce-9d3e-671e9110ece6` | 2025-07-15 | 4 | 2 |

**Sample plays:**

| Game | Order | Inn | Half | Outcome | Pitches | FPS |
|------|-------|-----|------|---------|---------|-----|
| `06715ac5-4d35-4c96-a945-d9593f63c68f` | 56 | 6 | bottom | Strikeout | 3 | 1 |
| `06715ac5-4d35-4c96-a945-d9593f63c68f` | 63 | 7 | bottom | Ground Out | 1 | 1 |
| `06715ac5-4d35-4c96-a945-d9593f63c68f` | 64 | 7 | bottom | Ground Out | 1 | 1 |
| `06715ac5-4d35-4c96-a945-d9593f63c68f` | 65 | 7 | bottom | Ground Out | 1 | 1 |
| `077a027a-f296-4784-9f94-a325f8b646dd` | 22 | 3 | top | Strikeout | 6 | 0 |

#### Kadyn Lichtenberg (Lincoln Rebels 14U)
Derived=113, GC=124, Diff=11 (8.9%)

**Per-game breakdown:**

| Game | Date | PAs | FPS Count |
|------|------|-----|-----------|
| `7ff3818e-2537-472d-b53d-9bd5b15d9894` | 2025-04-05 | 16 | 10 |
| `44dcf07d-e039-4a1b-a410-f3c9861c500e` | 2025-04-12 | 6 | 2 |
| `3c0d2389-0733-4119-911f-2c7b74872b43` | 2025-04-16 | 3 | 2 |
| `56f2bf82-d40c-45c9-9449-d95a41ee0892` | 2025-04-19 | 13 | 8 |
| `2514bd4d-ce1b-4871-9af5-268ddf5ba16e` | 2025-04-27 | 2 | 1 |
| `5728a6a4-c477-4307-9684-3533fb958c53` | 2025-04-27 | 5 | 3 |
| `3565d52b-7cd6-4400-9823-8d0a08aaa182` | 2025-04-30 | 7 | 4 |
| `d61d8836-d16e-474d-ac52-c394488deddb` | 2025-05-04 | 25 | 16 |
| `65bb31ba-b635-4ae2-9573-75730cd18ebb` | 2025-05-11 | 6 | 2 |
| `87a88e9b-c744-4c98-8f2b-1da5e2183340` | 2025-05-11 | 8 | 3 |
| `703e594d-049d-495c-98f1-d56b9699b5e2` | 2025-05-24 | 4 | 2 |
| `7d260fe7-6cbe-4750-b7ab-60f862cb8bcc` | 2025-05-25 | 1 | 1 |
| `95cb4227-f5b7-44d5-9368-2c42586b6d79` | 2025-05-25 | 10 | 8 |
| `27325678-5b01-4a13-8254-93a4fdf71cad` | 2025-05-29 | 3 | 2 |
| `373a803b-596b-429e-b27f-8bb272fa0e70` | 2025-05-31 | 22 | 8 |
| `0d8acfd0-5a41-474b-bf51-2ff2a2dc75b9` | 2025-06-08 | 8 | 5 |
| `492b3719-01c6-45d2-9444-1c6e2af41994` | 2025-06-10 | 9 | 9 |
| `b4913330-5c4c-4efe-be85-bc37f1407d3b` | 2025-06-15 | 3 | 2 |
| `ee8b48b2-24f6-4fde-8ab5-9a39958e2848` | 2025-06-22 | 12 | 9 |
| `49d13d90-3831-41cb-8def-da0162a77e67` | 2025-06-27 | 4 | 0 |
| `6a5260f1-569f-4adf-9876-b3f951ce2aef` | 2025-07-07 | 7 | 3 |
| `264c7b15-f1f7-421a-abd3-a4eec7e02eae` | 2025-07-12 | 14 | 13 |

**Sample plays:**

| Game | Order | Inn | Half | Outcome | Pitches | FPS |
|------|-------|-----|------|---------|---------|-----|
| `0d8acfd0-5a41-474b-bf51-2ff2a2dc75b9` | 39 | 4 | top | Walk | 7 | 1 |
| `0d8acfd0-5a41-474b-bf51-2ff2a2dc75b9` | 40 | 4 | top | Fly Out | 3 | 1 |
| `0d8acfd0-5a41-474b-bf51-2ff2a2dc75b9` | 41 | 4 | top | Single | 1 | 1 |
| `0d8acfd0-5a41-474b-bf51-2ff2a2dc75b9` | 42 | 4 | top | Pop Out | 2 | 0 |
| `0d8acfd0-5a41-474b-bf51-2ff2a2dc75b9` | 47 | 5 | top | Fly Out | 3 | 1 |

#### Keenan Treat (Lincoln Rebels 14U)
Derived=45, GC=48, Diff=3 (6.2%)

**Per-game breakdown:**

| Game | Date | PAs | FPS Count |
|------|------|-----|-----------|
| `d48ba0c2-4231-4fd6-830a-41e0ea1e32c3` | 2025-04-05 | 11 | 3 |
| `5fc0e97c-bd3f-4e04-b31e-c30ef2593edf` | 2025-04-11 | 18 | 11 |
| `c37ddf68-ac19-43c9-b694-27e837713415` | 2025-04-13 | 1 | 0 |
| `56f2bf82-d40c-45c9-9449-d95a41ee0892` | 2025-04-19 | 4 | 2 |
| `453df5f6-24d2-4ba9-a788-90647f0f4dd3` | 2025-04-26 | 6 | 3 |
| `fc8f3a88-e437-4d13-bd8b-48edb05108e0` | 2025-05-03 | 11 | 6 |
| `4e459783-e52a-4600-b53f-76c45fc3cdc4` | 2025-05-14 | 6 | 3 |
| `1c9e15d7-6405-4aae-b387-99bdad642cb6` | 2025-05-23 | 15 | 9 |
| `90a1a43d-5526-49a2-9c7a-5f79825f70ba` | 2025-05-27 | 10 | 2 |
| `311fd64a-b3a4-4033-897b-f74e2bb62e87` | 2025-06-12 | 13 | 6 |

**Sample plays:**

| Game | Order | Inn | Half | Outcome | Pitches | FPS |
|------|-------|-----|------|---------|---------|-----|
| `1c9e15d7-6405-4aae-b387-99bdad642cb6` | 5 | 1 | bottom | Fly Out | 1 | 1 |
| `1c9e15d7-6405-4aae-b387-99bdad642cb6` | 6 | 1 | bottom | Walk | 4 | 0 |
| `1c9e15d7-6405-4aae-b387-99bdad642cb6` | 7 | 1 | bottom | Fielder's Choice | 1 | 1 |
| `1c9e15d7-6405-4aae-b387-99bdad642cb6` | 8 | 1 | bottom | Strikeout | 4 | 1 |
| `1c9e15d7-6405-4aae-b387-99bdad642cb6` | 16 | 2 | bottom | Walk | 4 | 0 |

#### Oliver Hitz (Lincoln Rebels 14U)
Derived=59, GC=48, Diff=11 (22.9%)

**Per-game breakdown:**

| Game | Date | PAs | FPS Count |
|------|------|-----|-----------|
| `7ff3818e-2537-472d-b53d-9bd5b15d9894` | 2025-04-05 | 6 | 1 |
| `e3471c3b-8c6d-450c-9541-dd20107e9ace` | 2025-04-06 | 16 | 8 |
| `c37ddf68-ac19-43c9-b694-27e837713415` | 2025-04-13 | 9 | 4 |
| `453df5f6-24d2-4ba9-a788-90647f0f4dd3` | 2025-04-26 | 1 | 0 |
| `d225c0bf-4718-4ed9-96ae-2471cc9759a7` | 2025-05-07 | 5 | 1 |
| `4e459783-e52a-4600-b53f-76c45fc3cdc4` | 2025-05-14 | 12 | 6 |
| `7914a47d-f7cd-4e96-b5fc-b9dbae7175dc` | 2025-05-17 | 19 | 8 |
| `703e594d-049d-495c-98f1-d56b9699b5e2` | 2025-05-24 | 2 | 1 |
| `17a5495a-8983-449c-b2d6-d1fc87c89489` | 2025-05-28 | 14 | 8 |
| `aa114bc8-2071-45d9-aeed-9357937499e5` | 2025-06-10 | 11 | 6 |
| `5db6c410-2e37-4c5b-a83e-929b75d36998` | 2025-06-13 | 3 | 2 |
| `0373a710-7214-47cf-920c-ca73949ee929` | 2025-07-14 | 30 | 12 |
| `e5faf695-d9b4-4e83-9de0-edc36cf9d1b7` | 2025-07-15 | 4 | 2 |

**Sample plays:**

| Game | Order | Inn | Half | Outcome | Pitches | FPS |
|------|-------|-----|------|---------|---------|-----|
| `0373a710-7214-47cf-920c-ca73949ee929` | 4 | 1 | bottom | Single | 3 | 1 |
| `0373a710-7214-47cf-920c-ca73949ee929` | 5 | 1 | bottom | Pop Out | 5 | 0 |
| `0373a710-7214-47cf-920c-ca73949ee929` | 6 | 1 | bottom | Double | 3 | 1 |
| `0373a710-7214-47cf-920c-ca73949ee929` | 7 | 1 | bottom | Line Out | 5 | 0 |
| `0373a710-7214-47cf-920c-ca73949ee929` | 8 | 1 | bottom | Fly Out | 1 | 1 |

#### Owen Rodocker (Lincoln Rebels 14U)
Derived=199, GC=189, Diff=10 (5.3%)

**Per-game breakdown:**

| Game | Date | PAs | FPS Count |
|------|------|-----|-----------|
| `990ea59c-ef58-44f9-9da0-7980c1c66bdf` | 2025-04-02 | 1 | 0 |
| `e3471c3b-8c6d-450c-9541-dd20107e9ace` | 2025-04-06 | 17 | 13 |
| `44dcf07d-e039-4a1b-a410-f3c9861c500e` | 2025-04-12 | 19 | 7 |
| `3c0d2389-0733-4119-911f-2c7b74872b43` | 2025-04-16 | 9 | 3 |
| `56f2bf82-d40c-45c9-9449-d95a41ee0892` | 2025-04-19 | 21 | 8 |
| `2514bd4d-ce1b-4871-9af5-268ddf5ba16e` | 2025-04-27 | 21 | 12 |
| `07c39def-7720-49d8-83e7-c08c6055a557` | 2025-05-04 | 22 | 11 |
| `107b43c3-b3b2-406f-8f51-74ad25d5c913` | 2025-05-10 | 2 | 1 |
| `65bb31ba-b635-4ae2-9573-75730cd18ebb` | 2025-05-11 | 7 | 5 |
| `87a88e9b-c744-4c98-8f2b-1da5e2183340` | 2025-05-11 | 12 | 7 |
| `077a027a-f296-4784-9f94-a325f8b646dd` | 2025-05-17 | 9 | 5 |
| `f5885703-3bb2-4a2a-93cb-c072eb7b9d94` | 2025-05-18 | 17 | 9 |
| `4ffe4f10-3379-4e50-978f-e4e1ba78cde4` | 2025-05-24 | 19 | 12 |
| `acd30c20-2ee4-46d1-8720-3f9f95b9dc85` | 2025-05-25 | 13 | 10 |
| `27325678-5b01-4a13-8254-93a4fdf71cad` | 2025-05-29 | 10 | 5 |
| `e7201d3e-fb69-4dc7-8f82-868050c612f1` | 2025-05-31 | 2 | 0 |
| `40716575-284a-40f5-8de0-a7317ffd9913` | 2025-06-08 | 15 | 11 |
| `aa114bc8-2071-45d9-aeed-9357937499e5` | 2025-06-10 | 21 | 12 |
| `3b945477-27d6-41cd-ad0c-c4599f036f07` | 2025-06-14 | 8 | 5 |
| `446a5153-f9e7-4fbf-be52-b157e4d41de4` | 2025-06-21 | 9 | 6 |
| `6c2586df-8658-4f11-bb79-e208cd15c563` | 2025-06-22 | 30 | 16 |
| `8e4ed2d2-2271-441e-8304-9cc7b166cc62` | 2025-06-28 | 23 | 17 |
| `c5cb55c7-d8a5-4dab-90f9-3a117bdcbc55` | 2025-07-05 | 20 | 11 |
| `bd1f8d2c-fc33-4dfb-b936-f960567c9502` | 2025-07-07 | 8 | 4 |
| `86199e44-b708-4778-9b89-6e91d74ab9c8` | 2025-07-12 | 10 | 6 |
| `e5faf695-d9b4-4e83-9de0-edc36cf9d1b7` | 2025-07-15 | 8 | 3 |

**Sample plays:**

| Game | Order | Inn | Half | Outcome | Pitches | FPS |
|------|-------|-----|------|---------|---------|-----|
| `077a027a-f296-4784-9f94-a325f8b646dd` | 0 | 1 | top | Single | 6 | 1 |
| `077a027a-f296-4784-9f94-a325f8b646dd` | 2 | 1 | top | Single | 5 | 1 |
| `077a027a-f296-4784-9f94-a325f8b646dd` | 3 | 1 | top | Strikeout | 4 | 0 |
| `077a027a-f296-4784-9f94-a325f8b646dd` | 4 | 1 | top | Ground Out | 2 | 0 |
| `077a027a-f296-4784-9f94-a325f8b646dd` | 5 | 1 | top | Strikeout | 4 | 1 |

#### Reid Wilkinson (Lincoln Rebels 14U)
Derived=84, GC=90, Diff=6 (6.7%)

**Per-game breakdown:**

| Game | Date | PAs | FPS Count |
|------|------|-----|-----------|
| `d48ba0c2-4231-4fd6-830a-41e0ea1e32c3` | 2025-04-05 | 16 | 13 |
| `0bf3b9e3-3414-4961-b19b-d58dd82f84d4` | 2025-04-12 | 15 | 6 |
| `48c79654-eb57-4ea9-8a55-3f328b57e27e` | 2025-04-26 | 1 | 1 |
| `d225c0bf-4718-4ed9-96ae-2471cc9759a7` | 2025-05-07 | 12 | 6 |
| `3badec1a-f9dc-4912-8f57-5b668fa2d8e6` | 2025-05-10 | 11 | 9 |
| `7b3c3f89-c5da-4a0b-8040-3709f07d25c3` | 2025-05-18 | 24 | 16 |
| `95cb4227-f5b7-44d5-9368-2c42586b6d79` | 2025-05-25 | 11 | 7 |
| `4f368d04-ee78-4400-b8e8-45ae48b8b345` | 2025-06-01 | 20 | 12 |
| `0d8acfd0-5a41-474b-bf51-2ff2a2dc75b9` | 2025-06-08 | 5 | 3 |
| `311fd64a-b3a4-4033-897b-f74e2bb62e87` | 2025-06-12 | 10 | 8 |
| `6bfac025-58e1-432b-9eb6-906b92324a91` | 2025-06-14 | 3 | 3 |
| `6a5260f1-569f-4adf-9876-b3f951ce2aef` | 2025-07-07 | 3 | 0 |

**Sample plays:**

| Game | Order | Inn | Half | Outcome | Pitches | FPS |
|------|-------|-----|------|---------|---------|-----|
| `0bf3b9e3-3414-4961-b19b-d58dd82f84d4` | 4 | 1 | bottom | Single | 2 | 0 |
| `0bf3b9e3-3414-4961-b19b-d58dd82f84d4` | 5 | 1 | bottom | Walk | 4 | 0 |
| `0bf3b9e3-3414-4961-b19b-d58dd82f84d4` | 6 | 1 | bottom | Error | 3 | 0 |
| `0bf3b9e3-3414-4961-b19b-d58dd82f84d4` | 7 | 1 | bottom | Walk | 6 | 0 |
| `0bf3b9e3-3414-4961-b19b-d58dd82f84d4` | 8 | 1 | bottom | Strikeout | 5 | 0 |

#### Tanner Rahmatulla (Standing Bear Freshman Grizzlies)
Derived=10, GC=12, Diff=2 (16.7%)

**Per-game breakdown:**

| Game | Date | PAs | FPS Count |
|------|------|-----|-----------|
| `155bc5ef-3347-4b23-b4ed-4ea8f1e3e9c7` | 2026-03-20 | 5 | 2 |
| `903c7d39-ea42-4669-a621-9756be5fd8b1` | 2026-03-28 | 8 | 8 |

**Sample plays:**

| Game | Order | Inn | Half | Outcome | Pitches | FPS |
|------|-------|-----|------|---------|---------|-----|
| `155bc5ef-3347-4b23-b4ed-4ea8f1e3e9c7` | 19 | 2 | top | Walk | 6 | 0 |
| `155bc5ef-3347-4b23-b4ed-4ea8f1e3e9c7` | 20 | 2 | top | Strikeout | 7 | 0 |
| `155bc5ef-3347-4b23-b4ed-4ea8f1e3e9c7` | 32 | 3 | top | Walk | 5 | 1 |
| `155bc5ef-3347-4b23-b4ed-4ea8f1e3e9c7` | 33 | 3 | top | Walk | 7 | 0 |
| `155bc5ef-3347-4b23-b4ed-4ea8f1e3e9c7` | 34 | 3 | top | Single | 4 | 1 |

#### Thomas Saddler (Standing Bear Freshman Grizzlies)
Derived=22, GC=20, Diff=2 (10.0%)

**Per-game breakdown:**

| Game | Date | PAs | FPS Count |
|------|------|-----|-----------|
| `91d00308-a64a-4738-bb7a-7f5be266e1c1` | 2026-03-19 | 6 | 2 |
| `155bc5ef-3347-4b23-b4ed-4ea8f1e3e9c7` | 2026-03-20 | 3 | 2 |
| `374ca73f-342c-4f24-a5ca-af155e09e9d9` | 2026-03-25 | 10 | 8 |
| `cd30b1e3-85f8-4283-9249-47ad013a1f04` | 2026-03-28 | 7 | 2 |
| `2975658b-9608-4176-a3df-69aa45d00af3` | 2026-04-01 | 16 | 8 |

**Sample plays:**

| Game | Order | Inn | Half | Outcome | Pitches | FPS |
|------|-------|-----|------|---------|---------|-----|
| `155bc5ef-3347-4b23-b4ed-4ea8f1e3e9c7` | 0 | 1 | top | Single | 6 | 0 |
| `155bc5ef-3347-4b23-b4ed-4ea8f1e3e9c7` | 1 | 1 | top | Pop Out | 4 | 1 |
| `155bc5ef-3347-4b23-b4ed-4ea8f1e3e9c7` | 2 | 1 | top | Ground Out | 3 | 1 |
| `2975658b-9608-4176-a3df-69aa45d00af3` | 0 | 1 | top | Fly Out | 3 | 0 |
| `2975658b-9608-4176-a3df-69aa45d00af3` | 1 | 1 | top | Pop Out | 5 | 0 |

## QAB (Quality At-Bat) Comparison

**Overall match rate**: 53.8%
(14 of 26 batters within 5.0% tolerance)

| Player | Team | Derived | GC | Diff | % Diff | Status |
|--------|------|---------|----|------|--------|--------|
| Austin Rodocker | Lincoln Rebels 14U | 64 | 73 | 9 | 12.3% | MISMATCH |
| Beckett Meens | Lincoln Rebels 14U | 52 | 57 | 5 | 8.8% | MISMATCH |
| Brody Henninger | Standing Bear Freshman Grizzlies | 16 | 16 | 0 | 0.0% | OK |
| Brooks Good | Standing Bear Freshman Grizzlies | 4 | 4 | 0 | 0.0% | OK |
| Caiden Strauss | Standing Bear Freshman Grizzlies | 2 | 2 | 0 | 0.0% | OK |
| Chase Lightner | Lincoln Rebels 14U | 128 | 135 | 7 | 5.2% | MISMATCH |
| Cole Silvertrust | Standing Bear Freshman Grizzlies | 12 | 12 | 0 | 0.0% | OK |
| Easton Larkins | Standing Bear Freshman Grizzlies | 10 | 11 | 1 | 9.1% | MISMATCH |
| Evan Mittan-DeBuhr | Lincoln Rebels 14U | 62 | 67 | 5 | 7.5% | MISMATCH |
| Grant Oliver | Standing Bear Freshman Grizzlies | 12 | 12 | 0 | 0.0% | OK |
| Hudson Reimers | Lincoln Rebels 14U | 104 | 107 | 3 | 2.8% | OK |
| Jace Stanczyk | Standing Bear Freshman Grizzlies | 4 | 4 | 0 | 0.0% | OK |
| Kadyn Lichtenberg | Lincoln Rebels 14U | 126 | 131 | 5 | 3.8% | OK |
| Keenan Treat | Lincoln Rebels 14U | 98 | 108 | 10 | 9.3% | MISMATCH |
| Kyler Hoffman | Standing Bear Freshman Grizzlies | 10 | 10 | 0 | 0.0% | OK |
| Levin Nguyen | Standing Bear Freshman Grizzlies | 4 | 4 | 0 | 0.0% | OK |
| Liam Beiermann | Standing Bear Freshman Grizzlies | 5 | 5 | 0 | 0.0% | OK |
| Oliver Hitz | Lincoln Rebels 14U | 121 | 132 | 11 | 8.3% | MISMATCH |
| Owen Hemmingsen | Lincoln Rebels 14U | 93 | 99 | 6 | 6.1% | MISMATCH |
| Owen Robison | Standing Bear Freshman Grizzlies | 13 | 13 | 0 | 0.0% | OK |
| Owen Rodocker | Lincoln Rebels 14U | 118 | 130 | 12 | 9.2% | MISMATCH |
| Reid Wilkinson | Lincoln Rebels 14U | 80 | 85 | 5 | 5.9% | MISMATCH |
| Reid Wilkinson | Standing Bear Freshman Grizzlies | 8 | 8 | 0 | 0.0% | OK |
| Tanner Rahmatulla | Standing Bear Freshman Grizzlies | 16 | 17 | 1 | 5.9% | MISMATCH |
| Thomas Saddler | Standing Bear Freshman Grizzlies | 15 | 15 | 0 | 0.0% | OK |
| Truman Jackson | Lincoln Rebels 14U | 122 | 132 | 10 | 7.6% | MISMATCH |

### QAB Discrepancy Diagnostics

#### Austin Rodocker (Lincoln Rebels 14U)
Derived=64, GC=73, Diff=9 (12.3%)

**Per-game breakdown:**

| Game | Date | PAs | QAB Count |
|------|------|-----|-----------|
| `990ea59c-ef58-44f9-9da0-7980c1c66bdf` | 2025-04-02 | 3 | 2 |
| `d48ba0c2-4231-4fd6-830a-41e0ea1e32c3` | 2025-04-05 | 4 | 1 |
| `0b8d88cc-01fd-4077-b76d-f13022c271d2` | 2025-04-06 | 3 | 1 |
| `e3471c3b-8c6d-450c-9541-dd20107e9ace` | 2025-04-06 | 2 | 0 |
| `69ca1ed9-f933-407b-937f-d710f4d81c2d` | 2025-04-08 | 1 | 0 |
| `48c79654-eb57-4ea9-8a55-3f328b57e27e` | 2025-04-26 | 1 | 1 |
| `24fccda9-110e-4614-be8b-3cc821ba8527` | 2025-05-09 | 4 | 3 |
| `107b43c3-b3b2-406f-8f51-74ad25d5c913` | 2025-05-10 | 3 | 0 |
| `3badec1a-f9dc-4912-8f57-5b668fa2d8e6` | 2025-05-10 | 3 | 0 |
| `65bb31ba-b635-4ae2-9573-75730cd18ebb` | 2025-05-11 | 2 | 0 |
| `87a88e9b-c744-4c98-8f2b-1da5e2183340` | 2025-05-11 | 2 | 0 |
| `4e459783-e52a-4600-b53f-76c45fc3cdc4` | 2025-05-14 | 3 | 1 |
| `6f47dc77-0e41-4a28-87cd-bc9e8a32e958` | 2025-05-15 | 3 | 2 |
| `077a027a-f296-4784-9f94-a325f8b646dd` | 2025-05-17 | 2 | 0 |
| `7914a47d-f7cd-4e96-b5fc-b9dbae7175dc` | 2025-05-17 | 2 | 1 |
| `7b3c3f89-c5da-4a0b-8040-3709f07d25c3` | 2025-05-18 | 3 | 1 |
| `f5885703-3bb2-4a2a-93cb-c072eb7b9d94` | 2025-05-18 | 2 | 1 |
| `601a7a79-f536-4058-bdfc-02b148347501` | 2025-05-21 | 2 | 1 |
| `1c9e15d7-6405-4aae-b387-99bdad642cb6` | 2025-05-23 | 4 | 2 |
| `4ffe4f10-3379-4e50-978f-e4e1ba78cde4` | 2025-05-24 | 4 | 2 |
| `703e594d-049d-495c-98f1-d56b9699b5e2` | 2025-05-24 | 4 | 1 |
| `95cb4227-f5b7-44d5-9368-2c42586b6d79` | 2025-05-25 | 2 | 0 |
| `acd30c20-2ee4-46d1-8720-3f9f95b9dc85` | 2025-05-25 | 3 | 2 |
| `90a1a43d-5526-49a2-9c7a-5f79825f70ba` | 2025-05-27 | 1 | 0 |
| `17a5495a-8983-449c-b2d6-d1fc87c89489` | 2025-05-28 | 2 | 0 |
| `27325678-5b01-4a13-8254-93a4fdf71cad` | 2025-05-29 | 1 | 1 |
| `ffae764f-c426-4e35-9b18-b195598a2d41` | 2025-05-29 | 3 | 2 |
| `e1ae3e43-74c4-4a4d-a978-75ce82550af7` | 2025-05-30 | 3 | 0 |
| `373a803b-596b-429e-b27f-8bb272fa0e70` | 2025-05-31 | 2 | 0 |
| `e7201d3e-fb69-4dc7-8f82-868050c612f1` | 2025-05-31 | 4 | 2 |
| `4f368d04-ee78-4400-b8e8-45ae48b8b345` | 2025-06-01 | 1 | 1 |
| `a9452686-326b-41ea-a567-58bdf9552287` | 2025-06-01 | 2 | 1 |
| `37883b18-d42d-4b0a-a2e4-44fbac8233c9` | 2025-06-07 | 3 | 2 |
| `e0b95549-522c-4df5-9c47-108854c59f0e` | 2025-06-07 | 1 | 0 |
| `0d8acfd0-5a41-474b-bf51-2ff2a2dc75b9` | 2025-06-08 | 3 | 2 |
| `1b893d1d-c31d-4b95-a2e7-176e17e7bdde` | 2025-06-08 | 3 | 1 |
| `40716575-284a-40f5-8de0-a7317ffd9913` | 2025-06-08 | 1 | 0 |
| `492b3719-01c6-45d2-9444-1c6e2af41994` | 2025-06-10 | 3 | 3 |
| `aa114bc8-2071-45d9-aeed-9357937499e5` | 2025-06-10 | 3 | 1 |
| `311fd64a-b3a4-4033-897b-f74e2bb62e87` | 2025-06-12 | 3 | 0 |
| `5db6c410-2e37-4c5b-a83e-929b75d36998` | 2025-06-13 | 1 | 0 |
| `9bba250f-3123-4154-96da-c40d288e4603` | 2025-06-13 | 3 | 2 |
| `a6b45809-0b67-41eb-ac20-f03ffbdc1f1c` | 2025-06-13 | 3 | 1 |
| `6bfac025-58e1-432b-9eb6-906b92324a91` | 2025-06-14 | 2 | 1 |
| `b4913330-5c4c-4efe-be85-bc37f1407d3b` | 2025-06-15 | 2 | 0 |
| `34c07055-2653-4baa-9b68-9a451fd97052` | 2025-06-21 | 3 | 2 |
| `446a5153-f9e7-4fbf-be52-b157e4d41de4` | 2025-06-21 | 1 | 1 |
| `6c2586df-8658-4f11-bb79-e208cd15c563` | 2025-06-22 | 2 | 0 |
| `ee8b48b2-24f6-4fde-8ab5-9a39958e2848` | 2025-06-22 | 1 | 1 |
| `5b182ab0-aa12-44b7-8807-a464232474f0` | 2025-06-25 | 3 | 2 |
| `49d13d90-3831-41cb-8def-da0162a77e67` | 2025-06-27 | 3 | 2 |
| `870581ed-725c-4d31-99ca-2eabbad1101e` | 2025-06-27 | 3 | 0 |
| `8e4ed2d2-2271-441e-8304-9cc7b166cc62` | 2025-06-28 | 3 | 3 |
| `d932e5e8-d20c-4f7d-bc36-c77cca56e749` | 2025-06-28 | 1 | 1 |
| `63e53e8e-22df-460b-98e0-a5a9b0e77849` | 2025-06-29 | 3 | 0 |
| `c5cb55c7-d8a5-4dab-90f9-3a117bdcbc55` | 2025-07-05 | 4 | 1 |
| `63d14139-686a-4a50-8f3e-1de4eea67b80` | 2025-07-06 | 2 | 0 |
| `6a5260f1-569f-4adf-9876-b3f951ce2aef` | 2025-07-07 | 2 | 0 |
| `bd1f8d2c-fc33-4dfb-b936-f960567c9502` | 2025-07-07 | 4 | 3 |
| `264c7b15-f1f7-421a-abd3-a4eec7e02eae` | 2025-07-12 | 3 | 1 |
| `86199e44-b708-4778-9b89-6e91d74ab9c8` | 2025-07-12 | 2 | 0 |
| `67537faf-8d25-4aa5-86a5-6db8ae7a0e8f` | 2025-07-13 | 2 | 1 |
| `0373a710-7214-47cf-920c-ca73949ee929` | 2025-07-14 | 2 | 1 |
| `1e0f8dfc-a7cb-46ce-9d3e-671e9110ece6` | 2025-07-15 | 3 | 2 |
| `e5faf695-d9b4-4e83-9de0-edc36cf9d1b7` | 2025-07-15 | 1 | 1 |

**Sample plays:**

| Game | Order | Inn | Half | Outcome | Pitches | QAB |
|------|-------|-----|------|---------|---------|-----|
| `0373a710-7214-47cf-920c-ca73949ee929` | 9 | 2 | top | Walk | 8 | 1 |
| `0373a710-7214-47cf-920c-ca73949ee929` | 36 | 4 | top | Ground Out | 3 | 0 |
| `077a027a-f296-4784-9f94-a325f8b646dd` | 13 | 1 | bottom | Line Out | 2 | 0 |
| `077a027a-f296-4784-9f94-a325f8b646dd` | 58 | 6 | bottom | Hit By Pitch | 3 | 0 |
| `0b8d88cc-01fd-4077-b76d-f13022c271d2` | 4 | 1 | top | Walk | 4 | 1 |

#### Beckett Meens (Lincoln Rebels 14U)
Derived=52, GC=57, Diff=5 (8.8%)

**Per-game breakdown:**

| Game | Date | PAs | QAB Count |
|------|------|-----|-----------|
| `990ea59c-ef58-44f9-9da0-7980c1c66bdf` | 2025-04-02 | 2 | 2 |
| `3d31ce33-6983-4c4b-9e25-c0c1cfb0c27f` | 2025-04-04 | 3 | 1 |
| `7ff3818e-2537-472d-b53d-9bd5b15d9894` | 2025-04-05 | 3 | 1 |
| `9014514d-b923-4536-8b30-72029dd059a8` | 2025-04-05 | 3 | 3 |
| `d48ba0c2-4231-4fd6-830a-41e0ea1e32c3` | 2025-04-05 | 3 | 1 |
| `0b8d88cc-01fd-4077-b76d-f13022c271d2` | 2025-04-06 | 3 | 2 |
| `e3471c3b-8c6d-450c-9541-dd20107e9ace` | 2025-04-06 | 1 | 0 |
| `69ca1ed9-f933-407b-937f-d710f4d81c2d` | 2025-04-08 | 4 | 1 |
| `5fc0e97c-bd3f-4e04-b31e-c30ef2593edf` | 2025-04-11 | 4 | 1 |
| `0bf3b9e3-3414-4961-b19b-d58dd82f84d4` | 2025-04-12 | 4 | 0 |
| `44dcf07d-e039-4a1b-a410-f3c9861c500e` | 2025-04-12 | 4 | 2 |
| `4c91cd0b-33d4-463d-a9a4-181bc42aec9c` | 2025-04-13 | 3 | 1 |
| `c37ddf68-ac19-43c9-b694-27e837713415` | 2025-04-13 | 2 | 1 |
| `3c0d2389-0733-4119-911f-2c7b74872b43` | 2025-04-16 | 2 | 0 |
| `56f2bf82-d40c-45c9-9449-d95a41ee0892` | 2025-04-19 | 2 | 0 |
| `717fd9ea-7dac-478a-bcb9-0e83cf315e67` | 2025-04-20 | 1 | 0 |
| `3dcb2a12-7957-4b3f-9061-687069d0770b` | 2025-04-23 | 3 | 1 |
| `453df5f6-24d2-4ba9-a788-90647f0f4dd3` | 2025-04-26 | 3 | 2 |
| `48c79654-eb57-4ea9-8a55-3f328b57e27e` | 2025-04-26 | 3 | 2 |
| `2514bd4d-ce1b-4871-9af5-268ddf5ba16e` | 2025-04-27 | 3 | 0 |
| `5728a6a4-c477-4307-9684-3533fb958c53` | 2025-04-27 | 3 | 2 |
| `3565d52b-7cd6-4400-9823-8d0a08aaa182` | 2025-04-30 | 2 | 1 |
| `adfddd15-0633-4963-abbe-d7d3d8b1448b` | 2025-05-03 | 2 | 0 |
| `fc8f3a88-e437-4d13-bd8b-48edb05108e0` | 2025-05-03 | 2 | 1 |
| `d61d8836-d16e-474d-ac52-c394488deddb` | 2025-05-04 | 3 | 0 |
| `d225c0bf-4718-4ed9-96ae-2471cc9759a7` | 2025-05-07 | 3 | 2 |
| `24fccda9-110e-4614-be8b-3cc821ba8527` | 2025-05-09 | 4 | 1 |
| `107b43c3-b3b2-406f-8f51-74ad25d5c913` | 2025-05-10 | 3 | 0 |
| `3badec1a-f9dc-4912-8f57-5b668fa2d8e6` | 2025-05-10 | 1 | 1 |
| `4e459783-e52a-4600-b53f-76c45fc3cdc4` | 2025-05-14 | 3 | 2 |
| `6f47dc77-0e41-4a28-87cd-bc9e8a32e958` | 2025-05-15 | 4 | 1 |
| `077a027a-f296-4784-9f94-a325f8b646dd` | 2025-05-17 | 1 | 1 |
| `7914a47d-f7cd-4e96-b5fc-b9dbae7175dc` | 2025-05-17 | 1 | 0 |
| `601a7a79-f536-4058-bdfc-02b148347501` | 2025-05-21 | 1 | 0 |
| `1c9e15d7-6405-4aae-b387-99bdad642cb6` | 2025-05-23 | 4 | 2 |
| `4ffe4f10-3379-4e50-978f-e4e1ba78cde4` | 2025-05-24 | 2 | 0 |
| `703e594d-049d-495c-98f1-d56b9699b5e2` | 2025-05-24 | 2 | 0 |
| `90a1a43d-5526-49a2-9c7a-5f79825f70ba` | 2025-05-27 | 1 | 1 |
| `17a5495a-8983-449c-b2d6-d1fc87c89489` | 2025-05-28 | 2 | 1 |
| `27325678-5b01-4a13-8254-93a4fdf71cad` | 2025-05-29 | 2 | 2 |
| `ffae764f-c426-4e35-9b18-b195598a2d41` | 2025-05-29 | 3 | 2 |
| `e1ae3e43-74c4-4a4d-a978-75ce82550af7` | 2025-05-30 | 2 | 0 |
| `373a803b-596b-429e-b27f-8bb272fa0e70` | 2025-05-31 | 3 | 1 |
| `e7201d3e-fb69-4dc7-8f82-868050c612f1` | 2025-05-31 | 2 | 1 |
| `e0b95549-522c-4df5-9c47-108854c59f0e` | 2025-06-07 | 1 | 0 |
| `0d8acfd0-5a41-474b-bf51-2ff2a2dc75b9` | 2025-06-08 | 1 | 0 |
| `492b3719-01c6-45d2-9444-1c6e2af41994` | 2025-06-10 | 3 | 2 |
| `aa114bc8-2071-45d9-aeed-9357937499e5` | 2025-06-10 | 3 | 0 |
| `311fd64a-b3a4-4033-897b-f74e2bb62e87` | 2025-06-12 | 3 | 0 |
| `5db6c410-2e37-4c5b-a83e-929b75d36998` | 2025-06-13 | 3 | 0 |
| `a6b45809-0b67-41eb-ac20-f03ffbdc1f1c` | 2025-06-13 | 1 | 0 |
| `3b945477-27d6-41cd-ad0c-c4599f036f07` | 2025-06-14 | 1 | 0 |
| `6bfac025-58e1-432b-9eb6-906b92324a91` | 2025-06-14 | 2 | 0 |
| `446a5153-f9e7-4fbf-be52-b157e4d41de4` | 2025-06-21 | 1 | 1 |
| `6c2586df-8658-4f11-bb79-e208cd15c563` | 2025-06-22 | 1 | 0 |
| `49d13d90-3831-41cb-8def-da0162a77e67` | 2025-06-27 | 1 | 0 |
| `870581ed-725c-4d31-99ca-2eabbad1101e` | 2025-06-27 | 2 | 1 |
| `264c7b15-f1f7-421a-abd3-a4eec7e02eae` | 2025-07-12 | 2 | 2 |
| `86199e44-b708-4778-9b89-6e91d74ab9c8` | 2025-07-12 | 2 | 1 |
| `67537faf-8d25-4aa5-86a5-6db8ae7a0e8f` | 2025-07-13 | 2 | 1 |
| `0373a710-7214-47cf-920c-ca73949ee929` | 2025-07-14 | 2 | 1 |
| `e5faf695-d9b4-4e83-9de0-edc36cf9d1b7` | 2025-07-15 | 1 | 0 |

**Sample plays:**

| Game | Order | Inn | Half | Outcome | Pitches | QAB |
|------|-------|-----|------|---------|---------|-----|
| `0373a710-7214-47cf-920c-ca73949ee929` | 0 | 1 | top | Walk | 6 | 1 |
| `0373a710-7214-47cf-920c-ca73949ee929` | 26 | 3 | top | Fly Out | 3 | 0 |
| `077a027a-f296-4784-9f94-a325f8b646dd` | 39 | 4 | bottom | Ground Out | 6 | 1 |
| `0b8d88cc-01fd-4077-b76d-f13022c271d2` | 0 | 1 | top | Walk | 6 | 1 |
| `0b8d88cc-01fd-4077-b76d-f13022c271d2` | 9 | 1 | top | Walk | 5 | 1 |

#### Chase Lightner (Lincoln Rebels 14U)
Derived=128, GC=135, Diff=7 (5.2%)

**Per-game breakdown:**

| Game | Date | PAs | QAB Count |
|------|------|-----|-----------|
| `990ea59c-ef58-44f9-9da0-7980c1c66bdf` | 2025-04-02 | 3 | 1 |
| `3d31ce33-6983-4c4b-9e25-c0c1cfb0c27f` | 2025-04-04 | 4 | 1 |
| `7ff3818e-2537-472d-b53d-9bd5b15d9894` | 2025-04-05 | 3 | 1 |
| `9014514d-b923-4536-8b30-72029dd059a8` | 2025-04-05 | 4 | 2 |
| `d48ba0c2-4231-4fd6-830a-41e0ea1e32c3` | 2025-04-05 | 1 | 1 |
| `0b8d88cc-01fd-4077-b76d-f13022c271d2` | 2025-04-06 | 1 | 0 |
| `e3471c3b-8c6d-450c-9541-dd20107e9ace` | 2025-04-06 | 4 | 2 |
| `69ca1ed9-f933-407b-937f-d710f4d81c2d` | 2025-04-08 | 1 | 0 |
| `5fc0e97c-bd3f-4e04-b31e-c30ef2593edf` | 2025-04-11 | 3 | 1 |
| `0bf3b9e3-3414-4961-b19b-d58dd82f84d4` | 2025-04-12 | 3 | 2 |
| `44dcf07d-e039-4a1b-a410-f3c9861c500e` | 2025-04-12 | 4 | 4 |
| `ae709c04-debf-47d9-8fd3-3c327d714ae3` | 2025-04-12 | 4 | 3 |
| `4c91cd0b-33d4-463d-a9a4-181bc42aec9c` | 2025-04-13 | 5 | 2 |
| `c37ddf68-ac19-43c9-b694-27e837713415` | 2025-04-13 | 4 | 3 |
| `3c0d2389-0733-4119-911f-2c7b74872b43` | 2025-04-16 | 3 | 1 |
| `56f2bf82-d40c-45c9-9449-d95a41ee0892` | 2025-04-19 | 3 | 1 |
| `717fd9ea-7dac-478a-bcb9-0e83cf315e67` | 2025-04-20 | 3 | 2 |
| `3dcb2a12-7957-4b3f-9061-687069d0770b` | 2025-04-23 | 3 | 2 |
| `453df5f6-24d2-4ba9-a788-90647f0f4dd3` | 2025-04-26 | 3 | 2 |
| `2514bd4d-ce1b-4871-9af5-268ddf5ba16e` | 2025-04-27 | 3 | 2 |
| `5728a6a4-c477-4307-9684-3533fb958c53` | 2025-04-27 | 2 | 1 |
| `06715ac5-4d35-4c96-a945-d9593f63c68f` | 2025-04-28 | 4 | 0 |
| `3565d52b-7cd6-4400-9823-8d0a08aaa182` | 2025-04-30 | 3 | 0 |
| `adfddd15-0633-4963-abbe-d7d3d8b1448b` | 2025-05-03 | 4 | 2 |
| `fc8f3a88-e437-4d13-bd8b-48edb05108e0` | 2025-05-03 | 1 | 1 |
| `07c39def-7720-49d8-83e7-c08c6055a557` | 2025-05-04 | 4 | 2 |
| `d61d8836-d16e-474d-ac52-c394488deddb` | 2025-05-04 | 4 | 1 |
| `e2e6f43f-8671-4f0e-909d-f1642a7fc127` | 2025-05-04 | 4 | 2 |
| `d225c0bf-4718-4ed9-96ae-2471cc9759a7` | 2025-05-07 | 2 | 0 |
| `107b43c3-b3b2-406f-8f51-74ad25d5c913` | 2025-05-10 | 3 | 0 |
| `3badec1a-f9dc-4912-8f57-5b668fa2d8e6` | 2025-05-10 | 3 | 2 |
| `65bb31ba-b635-4ae2-9573-75730cd18ebb` | 2025-05-11 | 2 | 2 |
| `87a88e9b-c744-4c98-8f2b-1da5e2183340` | 2025-05-11 | 4 | 1 |
| `4e459783-e52a-4600-b53f-76c45fc3cdc4` | 2025-05-14 | 2 | 2 |
| `077a027a-f296-4784-9f94-a325f8b646dd` | 2025-05-17 | 3 | 1 |
| `7914a47d-f7cd-4e96-b5fc-b9dbae7175dc` | 2025-05-17 | 3 | 1 |
| `7b3c3f89-c5da-4a0b-8040-3709f07d25c3` | 2025-05-18 | 4 | 1 |
| `f5885703-3bb2-4a2a-93cb-c072eb7b9d94` | 2025-05-18 | 4 | 0 |
| `601a7a79-f536-4058-bdfc-02b148347501` | 2025-05-21 | 2 | 1 |
| `1c9e15d7-6405-4aae-b387-99bdad642cb6` | 2025-05-23 | 4 | 3 |
| `4ffe4f10-3379-4e50-978f-e4e1ba78cde4` | 2025-05-24 | 3 | 0 |
| `703e594d-049d-495c-98f1-d56b9699b5e2` | 2025-05-24 | 1 | 0 |
| `7d260fe7-6cbe-4750-b7ab-60f862cb8bcc` | 2025-05-25 | 4 | 3 |
| `95cb4227-f5b7-44d5-9368-2c42586b6d79` | 2025-05-25 | 3 | 1 |
| `acd30c20-2ee4-46d1-8720-3f9f95b9dc85` | 2025-05-25 | 4 | 4 |
| `90a1a43d-5526-49a2-9c7a-5f79825f70ba` | 2025-05-27 | 2 | 0 |
| `17a5495a-8983-449c-b2d6-d1fc87c89489` | 2025-05-28 | 3 | 2 |
| `27325678-5b01-4a13-8254-93a4fdf71cad` | 2025-05-29 | 3 | 1 |
| `e1ae3e43-74c4-4a4d-a978-75ce82550af7` | 2025-05-30 | 3 | 0 |
| `373a803b-596b-429e-b27f-8bb272fa0e70` | 2025-05-31 | 4 | 1 |
| `e7201d3e-fb69-4dc7-8f82-868050c612f1` | 2025-05-31 | 2 | 1 |
| `4f368d04-ee78-4400-b8e8-45ae48b8b345` | 2025-06-01 | 4 | 3 |
| `a9452686-326b-41ea-a567-58bdf9552287` | 2025-06-01 | 4 | 2 |
| `37883b18-d42d-4b0a-a2e4-44fbac8233c9` | 2025-06-07 | 3 | 3 |
| `e0b95549-522c-4df5-9c47-108854c59f0e` | 2025-06-07 | 3 | 1 |
| `0d8acfd0-5a41-474b-bf51-2ff2a2dc75b9` | 2025-06-08 | 3 | 3 |
| `1b893d1d-c31d-4b95-a2e7-176e17e7bdde` | 2025-06-08 | 4 | 2 |
| `40716575-284a-40f5-8de0-a7317ffd9913` | 2025-06-08 | 4 | 2 |
| `aa114bc8-2071-45d9-aeed-9357937499e5` | 2025-06-10 | 3 | 0 |
| `311fd64a-b3a4-4033-897b-f74e2bb62e87` | 2025-06-12 | 3 | 2 |
| `5db6c410-2e37-4c5b-a83e-929b75d36998` | 2025-06-13 | 3 | 1 |
| `9bba250f-3123-4154-96da-c40d288e4603` | 2025-06-13 | 4 | 3 |
| `a6b45809-0b67-41eb-ac20-f03ffbdc1f1c` | 2025-06-13 | 3 | 0 |
| `3b945477-27d6-41cd-ad0c-c4599f036f07` | 2025-06-14 | 3 | 2 |
| `6bfac025-58e1-432b-9eb6-906b92324a91` | 2025-06-14 | 2 | 0 |
| `b4913330-5c4c-4efe-be85-bc37f1407d3b` | 2025-06-15 | 4 | 3 |
| `34c07055-2653-4baa-9b68-9a451fd97052` | 2025-06-21 | 3 | 1 |
| `446a5153-f9e7-4fbf-be52-b157e4d41de4` | 2025-06-21 | 4 | 3 |
| `6c2586df-8658-4f11-bb79-e208cd15c563` | 2025-06-22 | 5 | 3 |
| `ee8b48b2-24f6-4fde-8ab5-9a39958e2848` | 2025-06-22 | 3 | 2 |
| `5b182ab0-aa12-44b7-8807-a464232474f0` | 2025-06-25 | 3 | 0 |
| `49d13d90-3831-41cb-8def-da0162a77e67` | 2025-06-27 | 2 | 1 |
| `870581ed-725c-4d31-99ca-2eabbad1101e` | 2025-06-27 | 3 | 2 |
| `8e4ed2d2-2271-441e-8304-9cc7b166cc62` | 2025-06-28 | 3 | 2 |
| `d932e5e8-d20c-4f7d-bc36-c77cca56e749` | 2025-06-28 | 4 | 0 |
| `63e53e8e-22df-460b-98e0-a5a9b0e77849` | 2025-06-29 | 3 | 0 |
| `06852f3e-6626-40a2-bd17-7f18a92cb936` | 2025-07-05 | 3 | 0 |
| `c5cb55c7-d8a5-4dab-90f9-3a117bdcbc55` | 2025-07-05 | 4 | 2 |
| `63d14139-686a-4a50-8f3e-1de4eea67b80` | 2025-07-06 | 3 | 2 |
| `6a5260f1-569f-4adf-9876-b3f951ce2aef` | 2025-07-07 | 2 | 1 |
| `bd1f8d2c-fc33-4dfb-b936-f960567c9502` | 2025-07-07 | 5 | 2 |
| `264c7b15-f1f7-421a-abd3-a4eec7e02eae` | 2025-07-12 | 3 | 2 |
| `86199e44-b708-4778-9b89-6e91d74ab9c8` | 2025-07-12 | 3 | 2 |
| `67537faf-8d25-4aa5-86a5-6db8ae7a0e8f` | 2025-07-13 | 3 | 2 |
| `0373a710-7214-47cf-920c-ca73949ee929` | 2025-07-14 | 2 | 2 |
| `1e0f8dfc-a7cb-46ce-9d3e-671e9110ece6` | 2025-07-15 | 3 | 3 |
| `e5faf695-d9b4-4e83-9de0-edc36cf9d1b7` | 2025-07-15 | 1 | 0 |

**Sample plays:**

| Game | Order | Inn | Half | Outcome | Pitches | QAB |
|------|-------|-----|------|---------|---------|-----|
| `0373a710-7214-47cf-920c-ca73949ee929` | 15 | 2 | top | Walk | 4 | 1 |
| `0373a710-7214-47cf-920c-ca73949ee929` | 47 | 5 | top | Error | 4 | 1 |
| `06715ac5-4d35-4c96-a945-d9593f63c68f` | 0 | 1 | top | Ground Out | 4 | 0 |
| `06715ac5-4d35-4c96-a945-d9593f63c68f` | 17 | 3 | top | Single | 5 | 0 |
| `06715ac5-4d35-4c96-a945-d9593f63c68f` | 32 | 4 | top | Single | 2 | 0 |

#### Easton Larkins (Standing Bear Freshman Grizzlies)
Derived=10, GC=11, Diff=1 (9.1%)

**Per-game breakdown:**

| Game | Date | PAs | QAB Count |
|------|------|-----|-----------|
| `91d00308-a64a-4738-bb7a-7f5be266e1c1` | 2026-03-19 | 2 | 1 |
| `155bc5ef-3347-4b23-b4ed-4ea8f1e3e9c7` | 2026-03-20 | 2 | 1 |
| `757c024c-de8d-4b44-b159-7704a6ff0640` | 2026-03-21 | 1 | 1 |
| `374ca73f-342c-4f24-a5ca-af155e09e9d9` | 2026-03-25 | 3 | 2 |
| `a31f3884-456d-484b-a5c8-8df3333e3de7` | 2026-03-26 | 4 | 2 |
| `903c7d39-ea42-4669-a621-9756be5fd8b1` | 2026-03-28 | 4 | 0 |
| `cd30b1e3-85f8-4283-9249-47ad013a1f04` | 2026-03-28 | 2 | 1 |
| `72e91b67-2d01-4821-9a63-9c7958a5afe9` | 2026-03-30 | 1 | 1 |
| `2975658b-9608-4176-a3df-69aa45d00af3` | 2026-04-01 | 3 | 1 |

**Sample plays:**

| Game | Order | Inn | Half | Outcome | Pitches | QAB |
|------|-------|-----|------|---------|---------|-----|
| `155bc5ef-3347-4b23-b4ed-4ea8f1e3e9c7` | 9 | 1 | bottom | Fly Out | 1 | 0 |
| `155bc5ef-3347-4b23-b4ed-4ea8f1e3e9c7` | 29 | 2 | bottom | Walk | 5 | 1 |
| `2975658b-9608-4176-a3df-69aa45d00af3` | 31 | 3 | bottom | Ground Out | 2 | 0 |
| `2975658b-9608-4176-a3df-69aa45d00af3` | 51 | 5 | bottom | Single | 4 | 0 |
| `2975658b-9608-4176-a3df-69aa45d00af3` | 70 | 7 | bottom | Single | 6 | 1 |

#### Evan Mittan-DeBuhr (Lincoln Rebels 14U)
Derived=62, GC=67, Diff=5 (7.5%)

**Per-game breakdown:**

| Game | Date | PAs | QAB Count |
|------|------|-----|-----------|
| `990ea59c-ef58-44f9-9da0-7980c1c66bdf` | 2025-04-02 | 3 | 1 |
| `3d31ce33-6983-4c4b-9e25-c0c1cfb0c27f` | 2025-04-04 | 3 | 3 |
| `7ff3818e-2537-472d-b53d-9bd5b15d9894` | 2025-04-05 | 3 | 1 |
| `9014514d-b923-4536-8b30-72029dd059a8` | 2025-04-05 | 4 | 2 |
| `d48ba0c2-4231-4fd6-830a-41e0ea1e32c3` | 2025-04-05 | 4 | 1 |
| `0b8d88cc-01fd-4077-b76d-f13022c271d2` | 2025-04-06 | 3 | 0 |
| `e3471c3b-8c6d-450c-9541-dd20107e9ace` | 2025-04-06 | 2 | 2 |
| `69ca1ed9-f933-407b-937f-d710f4d81c2d` | 2025-04-08 | 3 | 0 |
| `5fc0e97c-bd3f-4e04-b31e-c30ef2593edf` | 2025-04-11 | 4 | 1 |
| `0bf3b9e3-3414-4961-b19b-d58dd82f84d4` | 2025-04-12 | 2 | 2 |
| `44dcf07d-e039-4a1b-a410-f3c9861c500e` | 2025-04-12 | 3 | 1 |
| `ae709c04-debf-47d9-8fd3-3c327d714ae3` | 2025-04-12 | 3 | 0 |
| `4c91cd0b-33d4-463d-a9a4-181bc42aec9c` | 2025-04-13 | 1 | 0 |
| `c37ddf68-ac19-43c9-b694-27e837713415` | 2025-04-13 | 3 | 1 |
| `3c0d2389-0733-4119-911f-2c7b74872b43` | 2025-04-16 | 2 | 0 |
| `56f2bf82-d40c-45c9-9449-d95a41ee0892` | 2025-04-19 | 1 | 0 |
| `717fd9ea-7dac-478a-bcb9-0e83cf315e67` | 2025-04-20 | 4 | 1 |
| `3dcb2a12-7957-4b3f-9061-687069d0770b` | 2025-04-23 | 2 | 1 |
| `453df5f6-24d2-4ba9-a788-90647f0f4dd3` | 2025-04-26 | 3 | 1 |
| `48c79654-eb57-4ea9-8a55-3f328b57e27e` | 2025-04-26 | 3 | 0 |
| `5728a6a4-c477-4307-9684-3533fb958c53` | 2025-04-27 | 1 | 0 |
| `06715ac5-4d35-4c96-a945-d9593f63c68f` | 2025-04-28 | 3 | 2 |
| `3565d52b-7cd6-4400-9823-8d0a08aaa182` | 2025-04-30 | 2 | 0 |
| `adfddd15-0633-4963-abbe-d7d3d8b1448b` | 2025-05-03 | 2 | 0 |
| `fc8f3a88-e437-4d13-bd8b-48edb05108e0` | 2025-05-03 | 4 | 1 |
| `07c39def-7720-49d8-83e7-c08c6055a557` | 2025-05-04 | 3 | 2 |
| `e2e6f43f-8671-4f0e-909d-f1642a7fc127` | 2025-05-04 | 1 | 0 |
| `d225c0bf-4718-4ed9-96ae-2471cc9759a7` | 2025-05-07 | 3 | 0 |
| `24fccda9-110e-4614-be8b-3cc821ba8527` | 2025-05-09 | 3 | 0 |
| `3badec1a-f9dc-4912-8f57-5b668fa2d8e6` | 2025-05-10 | 3 | 2 |
| `87a88e9b-c744-4c98-8f2b-1da5e2183340` | 2025-05-11 | 1 | 0 |
| `4e459783-e52a-4600-b53f-76c45fc3cdc4` | 2025-05-14 | 3 | 3 |
| `6f47dc77-0e41-4a28-87cd-bc9e8a32e958` | 2025-05-15 | 3 | 1 |
| `7914a47d-f7cd-4e96-b5fc-b9dbae7175dc` | 2025-05-17 | 1 | 0 |
| `f5885703-3bb2-4a2a-93cb-c072eb7b9d94` | 2025-05-18 | 1 | 0 |
| `601a7a79-f536-4058-bdfc-02b148347501` | 2025-05-21 | 1 | 1 |
| `1c9e15d7-6405-4aae-b387-99bdad642cb6` | 2025-05-23 | 4 | 2 |
| `4ffe4f10-3379-4e50-978f-e4e1ba78cde4` | 2025-05-24 | 2 | 0 |
| `703e594d-049d-495c-98f1-d56b9699b5e2` | 2025-05-24 | 2 | 0 |
| `90a1a43d-5526-49a2-9c7a-5f79825f70ba` | 2025-05-27 | 1 | 0 |
| `17a5495a-8983-449c-b2d6-d1fc87c89489` | 2025-05-28 | 2 | 1 |
| `27325678-5b01-4a13-8254-93a4fdf71cad` | 2025-05-29 | 2 | 2 |
| `ffae764f-c426-4e35-9b18-b195598a2d41` | 2025-05-29 | 3 | 2 |
| `e1ae3e43-74c4-4a4d-a978-75ce82550af7` | 2025-05-30 | 2 | 2 |
| `373a803b-596b-429e-b27f-8bb272fa0e70` | 2025-05-31 | 2 | 1 |
| `e7201d3e-fb69-4dc7-8f82-868050c612f1` | 2025-05-31 | 3 | 1 |
| `0d8acfd0-5a41-474b-bf51-2ff2a2dc75b9` | 2025-06-08 | 1 | 1 |
| `492b3719-01c6-45d2-9444-1c6e2af41994` | 2025-06-10 | 4 | 1 |
| `aa114bc8-2071-45d9-aeed-9357937499e5` | 2025-06-10 | 3 | 2 |
| `311fd64a-b3a4-4033-897b-f74e2bb62e87` | 2025-06-12 | 3 | 0 |
| `5db6c410-2e37-4c5b-a83e-929b75d36998` | 2025-06-13 | 2 | 2 |
| `9bba250f-3123-4154-96da-c40d288e4603` | 2025-06-13 | 1 | 0 |
| `a6b45809-0b67-41eb-ac20-f03ffbdc1f1c` | 2025-06-13 | 2 | 2 |
| `3b945477-27d6-41cd-ad0c-c4599f036f07` | 2025-06-14 | 1 | 0 |
| `b4913330-5c4c-4efe-be85-bc37f1407d3b` | 2025-06-15 | 1 | 0 |
| `34c07055-2653-4baa-9b68-9a451fd97052` | 2025-06-21 | 3 | 2 |
| `446a5153-f9e7-4fbf-be52-b157e4d41de4` | 2025-06-21 | 2 | 2 |
| `6c2586df-8658-4f11-bb79-e208cd15c563` | 2025-06-22 | 2 | 2 |
| `ee8b48b2-24f6-4fde-8ab5-9a39958e2848` | 2025-06-22 | 1 | 1 |
| `49d13d90-3831-41cb-8def-da0162a77e67` | 2025-06-27 | 1 | 0 |
| `870581ed-725c-4d31-99ca-2eabbad1101e` | 2025-06-27 | 1 | 1 |
| `8e4ed2d2-2271-441e-8304-9cc7b166cc62` | 2025-06-28 | 2 | 0 |
| `d932e5e8-d20c-4f7d-bc36-c77cca56e749` | 2025-06-28 | 2 | 1 |
| `63e53e8e-22df-460b-98e0-a5a9b0e77849` | 2025-06-29 | 2 | 0 |
| `c5cb55c7-d8a5-4dab-90f9-3a117bdcbc55` | 2025-07-05 | 2 | 0 |
| `264c7b15-f1f7-421a-abd3-a4eec7e02eae` | 2025-07-12 | 2 | 1 |
| `86199e44-b708-4778-9b89-6e91d74ab9c8` | 2025-07-12 | 2 | 0 |
| `67537faf-8d25-4aa5-86a5-6db8ae7a0e8f` | 2025-07-13 | 2 | 1 |
| `0373a710-7214-47cf-920c-ca73949ee929` | 2025-07-14 | 2 | 2 |

**Sample plays:**

| Game | Order | Inn | Half | Outcome | Pitches | QAB |
|------|-------|-----|------|---------|---------|-----|
| `0373a710-7214-47cf-920c-ca73949ee929` | 1 | 1 | top | Strikeout | 5 | 1 |
| `0373a710-7214-47cf-920c-ca73949ee929` | 27 | 3 | top | Strikeout | 6 | 1 |
| `06715ac5-4d35-4c96-a945-d9593f63c68f` | 13 | 2 | top | Strikeout | 6 | 1 |
| `06715ac5-4d35-4c96-a945-d9593f63c68f` | 31 | 4 | top | Fly Out | 6 | 1 |
| `06715ac5-4d35-4c96-a945-d9593f63c68f` | 62 | 7 | top | Strikeout | 4 | 0 |

#### Keenan Treat (Lincoln Rebels 14U)
Derived=98, GC=108, Diff=10 (9.3%)

**Per-game breakdown:**

| Game | Date | PAs | QAB Count |
|------|------|-----|-----------|
| `990ea59c-ef58-44f9-9da0-7980c1c66bdf` | 2025-04-02 | 2 | 1 |
| `3d31ce33-6983-4c4b-9e25-c0c1cfb0c27f` | 2025-04-04 | 3 | 1 |
| `7ff3818e-2537-472d-b53d-9bd5b15d9894` | 2025-04-05 | 3 | 2 |
| `9014514d-b923-4536-8b30-72029dd059a8` | 2025-04-05 | 4 | 4 |
| `d48ba0c2-4231-4fd6-830a-41e0ea1e32c3` | 2025-04-05 | 3 | 1 |
| `0b8d88cc-01fd-4077-b76d-f13022c271d2` | 2025-04-06 | 4 | 3 |
| `e3471c3b-8c6d-450c-9541-dd20107e9ace` | 2025-04-06 | 2 | 1 |
| `69ca1ed9-f933-407b-937f-d710f4d81c2d` | 2025-04-08 | 3 | 2 |
| `5fc0e97c-bd3f-4e04-b31e-c30ef2593edf` | 2025-04-11 | 4 | 3 |
| `0bf3b9e3-3414-4961-b19b-d58dd82f84d4` | 2025-04-12 | 2 | 2 |
| `44dcf07d-e039-4a1b-a410-f3c9861c500e` | 2025-04-12 | 3 | 3 |
| `ae709c04-debf-47d9-8fd3-3c327d714ae3` | 2025-04-12 | 3 | 0 |
| `4c91cd0b-33d4-463d-a9a4-181bc42aec9c` | 2025-04-13 | 4 | 1 |
| `c37ddf68-ac19-43c9-b694-27e837713415` | 2025-04-13 | 1 | 0 |
| `3c0d2389-0733-4119-911f-2c7b74872b43` | 2025-04-16 | 2 | 0 |
| `56f2bf82-d40c-45c9-9449-d95a41ee0892` | 2025-04-19 | 2 | 2 |
| `717fd9ea-7dac-478a-bcb9-0e83cf315e67` | 2025-04-20 | 1 | 1 |
| `3dcb2a12-7957-4b3f-9061-687069d0770b` | 2025-04-23 | 3 | 2 |
| `453df5f6-24d2-4ba9-a788-90647f0f4dd3` | 2025-04-26 | 3 | 3 |
| `48c79654-eb57-4ea9-8a55-3f328b57e27e` | 2025-04-26 | 3 | 0 |
| `2514bd4d-ce1b-4871-9af5-268ddf5ba16e` | 2025-04-27 | 3 | 0 |
| `5728a6a4-c477-4307-9684-3533fb958c53` | 2025-04-27 | 3 | 2 |
| `06715ac5-4d35-4c96-a945-d9593f63c68f` | 2025-04-28 | 1 | 0 |
| `3565d52b-7cd6-4400-9823-8d0a08aaa182` | 2025-04-30 | 3 | 3 |
| `adfddd15-0633-4963-abbe-d7d3d8b1448b` | 2025-05-03 | 3 | 1 |
| `fc8f3a88-e437-4d13-bd8b-48edb05108e0` | 2025-05-03 | 3 | 0 |
| `07c39def-7720-49d8-83e7-c08c6055a557` | 2025-05-04 | 4 | 3 |
| `d61d8836-d16e-474d-ac52-c394488deddb` | 2025-05-04 | 4 | 2 |
| `e2e6f43f-8671-4f0e-909d-f1642a7fc127` | 2025-05-04 | 4 | 0 |
| `d225c0bf-4718-4ed9-96ae-2471cc9759a7` | 2025-05-07 | 3 | 1 |
| `24fccda9-110e-4614-be8b-3cc821ba8527` | 2025-05-09 | 4 | 2 |
| `3badec1a-f9dc-4912-8f57-5b668fa2d8e6` | 2025-05-10 | 3 | 2 |
| `87a88e9b-c744-4c98-8f2b-1da5e2183340` | 2025-05-11 | 4 | 2 |
| `4e459783-e52a-4600-b53f-76c45fc3cdc4` | 2025-05-14 | 2 | 0 |
| `077a027a-f296-4784-9f94-a325f8b646dd` | 2025-05-17 | 3 | 1 |
| `7914a47d-f7cd-4e96-b5fc-b9dbae7175dc` | 2025-05-17 | 2 | 0 |
| `7b3c3f89-c5da-4a0b-8040-3709f07d25c3` | 2025-05-18 | 4 | 3 |
| `f5885703-3bb2-4a2a-93cb-c072eb7b9d94` | 2025-05-18 | 3 | 1 |
| `601a7a79-f536-4058-bdfc-02b148347501` | 2025-05-21 | 2 | 0 |
| `1c9e15d7-6405-4aae-b387-99bdad642cb6` | 2025-05-23 | 4 | 1 |
| `703e594d-049d-495c-98f1-d56b9699b5e2` | 2025-05-24 | 3 | 1 |
| `7d260fe7-6cbe-4750-b7ab-60f862cb8bcc` | 2025-05-25 | 4 | 4 |
| `acd30c20-2ee4-46d1-8720-3f9f95b9dc85` | 2025-05-25 | 3 | 2 |
| `90a1a43d-5526-49a2-9c7a-5f79825f70ba` | 2025-05-27 | 2 | 0 |
| `17a5495a-8983-449c-b2d6-d1fc87c89489` | 2025-05-28 | 2 | 0 |
| `27325678-5b01-4a13-8254-93a4fdf71cad` | 2025-05-29 | 1 | 1 |
| `ffae764f-c426-4e35-9b18-b195598a2d41` | 2025-05-29 | 3 | 2 |
| `e1ae3e43-74c4-4a4d-a978-75ce82550af7` | 2025-05-30 | 4 | 1 |
| `373a803b-596b-429e-b27f-8bb272fa0e70` | 2025-05-31 | 3 | 1 |
| `e7201d3e-fb69-4dc7-8f82-868050c612f1` | 2025-05-31 | 4 | 0 |
| `4f368d04-ee78-4400-b8e8-45ae48b8b345` | 2025-06-01 | 3 | 1 |
| `a9452686-326b-41ea-a567-58bdf9552287` | 2025-06-01 | 4 | 2 |
| `37883b18-d42d-4b0a-a2e4-44fbac8233c9` | 2025-06-07 | 3 | 2 |
| `0d8acfd0-5a41-474b-bf51-2ff2a2dc75b9` | 2025-06-08 | 1 | 1 |
| `1b893d1d-c31d-4b95-a2e7-176e17e7bdde` | 2025-06-08 | 3 | 2 |
| `40716575-284a-40f5-8de0-a7317ffd9913` | 2025-06-08 | 3 | 1 |
| `492b3719-01c6-45d2-9444-1c6e2af41994` | 2025-06-10 | 4 | 1 |
| `aa114bc8-2071-45d9-aeed-9357937499e5` | 2025-06-10 | 3 | 1 |
| `311fd64a-b3a4-4033-897b-f74e2bb62e87` | 2025-06-12 | 4 | 3 |
| `5db6c410-2e37-4c5b-a83e-929b75d36998` | 2025-06-13 | 3 | 1 |
| `9bba250f-3123-4154-96da-c40d288e4603` | 2025-06-13 | 1 | 1 |
| `3b945477-27d6-41cd-ad0c-c4599f036f07` | 2025-06-14 | 1 | 0 |
| `6bfac025-58e1-432b-9eb6-906b92324a91` | 2025-06-14 | 2 | 0 |
| `b4913330-5c4c-4efe-be85-bc37f1407d3b` | 2025-06-15 | 3 | 2 |
| `446a5153-f9e7-4fbf-be52-b157e4d41de4` | 2025-06-21 | 3 | 2 |
| `6c2586df-8658-4f11-bb79-e208cd15c563` | 2025-06-22 | 3 | 1 |
| `ee8b48b2-24f6-4fde-8ab5-9a39958e2848` | 2025-06-22 | 3 | 2 |
| `5b182ab0-aa12-44b7-8807-a464232474f0` | 2025-06-25 | 3 | 1 |
| `49d13d90-3831-41cb-8def-da0162a77e67` | 2025-06-27 | 3 | 1 |
| `06852f3e-6626-40a2-bd17-7f18a92cb936` | 2025-07-05 | 2 | 0 |
| `6a5260f1-569f-4adf-9876-b3f951ce2aef` | 2025-07-07 | 2 | 0 |
| `264c7b15-f1f7-421a-abd3-a4eec7e02eae` | 2025-07-12 | 3 | 2 |
| `86199e44-b708-4778-9b89-6e91d74ab9c8` | 2025-07-12 | 2 | 2 |
| `67537faf-8d25-4aa5-86a5-6db8ae7a0e8f` | 2025-07-13 | 2 | 0 |
| `0373a710-7214-47cf-920c-ca73949ee929` | 2025-07-14 | 2 | 0 |
| `1e0f8dfc-a7cb-46ce-9d3e-671e9110ece6` | 2025-07-15 | 1 | 1 |
| `e5faf695-d9b4-4e83-9de0-edc36cf9d1b7` | 2025-07-15 | 1 | 0 |

**Sample plays:**

| Game | Order | Inn | Half | Outcome | Pitches | QAB |
|------|-------|-----|------|---------|---------|-----|
| `0373a710-7214-47cf-920c-ca73949ee929` | 2 | 1 | top | Ground Out | 1 | 0 |
| `0373a710-7214-47cf-920c-ca73949ee929` | 28 | 3 | top | Single | 2 | 0 |
| `06715ac5-4d35-4c96-a945-d9593f63c68f` | 48 | 6 | top | Strikeout | 3 | 0 |
| `06852f3e-6626-40a2-bd17-7f18a92cb936` | 18 | 2 | bottom | Error | 3 | 0 |
| `06852f3e-6626-40a2-bd17-7f18a92cb936` | 34 | 3 | bottom | Ground Out | 3 | 0 |

#### Oliver Hitz (Lincoln Rebels 14U)
Derived=121, GC=132, Diff=11 (8.3%)

**Per-game breakdown:**

| Game | Date | PAs | QAB Count |
|------|------|-----|-----------|
| `990ea59c-ef58-44f9-9da0-7980c1c66bdf` | 2025-04-02 | 3 | 0 |
| `3d31ce33-6983-4c4b-9e25-c0c1cfb0c27f` | 2025-04-04 | 3 | 3 |
| `7ff3818e-2537-472d-b53d-9bd5b15d9894` | 2025-04-05 | 3 | 1 |
| `9014514d-b923-4536-8b30-72029dd059a8` | 2025-04-05 | 4 | 3 |
| `d48ba0c2-4231-4fd6-830a-41e0ea1e32c3` | 2025-04-05 | 3 | 2 |
| `0b8d88cc-01fd-4077-b76d-f13022c271d2` | 2025-04-06 | 4 | 1 |
| `e3471c3b-8c6d-450c-9541-dd20107e9ace` | 2025-04-06 | 4 | 1 |
| `69ca1ed9-f933-407b-937f-d710f4d81c2d` | 2025-04-08 | 1 | 0 |
| `5fc0e97c-bd3f-4e04-b31e-c30ef2593edf` | 2025-04-11 | 1 | 1 |
| `0bf3b9e3-3414-4961-b19b-d58dd82f84d4` | 2025-04-12 | 3 | 1 |
| `44dcf07d-e039-4a1b-a410-f3c9861c500e` | 2025-04-12 | 4 | 4 |
| `ae709c04-debf-47d9-8fd3-3c327d714ae3` | 2025-04-12 | 4 | 3 |
| `4c91cd0b-33d4-463d-a9a4-181bc42aec9c` | 2025-04-13 | 5 | 3 |
| `c37ddf68-ac19-43c9-b694-27e837713415` | 2025-04-13 | 2 | 2 |
| `3c0d2389-0733-4119-911f-2c7b74872b43` | 2025-04-16 | 3 | 0 |
| `56f2bf82-d40c-45c9-9449-d95a41ee0892` | 2025-04-19 | 3 | 1 |
| `717fd9ea-7dac-478a-bcb9-0e83cf315e67` | 2025-04-20 | 4 | 1 |
| `3dcb2a12-7957-4b3f-9061-687069d0770b` | 2025-04-23 | 3 | 1 |
| `453df5f6-24d2-4ba9-a788-90647f0f4dd3` | 2025-04-26 | 3 | 1 |
| `2514bd4d-ce1b-4871-9af5-268ddf5ba16e` | 2025-04-27 | 3 | 1 |
| `5728a6a4-c477-4307-9684-3533fb958c53` | 2025-04-27 | 2 | 2 |
| `06715ac5-4d35-4c96-a945-d9593f63c68f` | 2025-04-28 | 4 | 2 |
| `3565d52b-7cd6-4400-9823-8d0a08aaa182` | 2025-04-30 | 3 | 1 |
| `adfddd15-0633-4963-abbe-d7d3d8b1448b` | 2025-05-03 | 3 | 3 |
| `fc8f3a88-e437-4d13-bd8b-48edb05108e0` | 2025-05-03 | 2 | 1 |
| `07c39def-7720-49d8-83e7-c08c6055a557` | 2025-05-04 | 3 | 2 |
| `d61d8836-d16e-474d-ac52-c394488deddb` | 2025-05-04 | 4 | 1 |
| `e2e6f43f-8671-4f0e-909d-f1642a7fc127` | 2025-05-04 | 4 | 0 |
| `d225c0bf-4718-4ed9-96ae-2471cc9759a7` | 2025-05-07 | 2 | 0 |
| `24fccda9-110e-4614-be8b-3cc821ba8527` | 2025-05-09 | 4 | 4 |
| `107b43c3-b3b2-406f-8f51-74ad25d5c913` | 2025-05-10 | 2 | 0 |
| `65bb31ba-b635-4ae2-9573-75730cd18ebb` | 2025-05-11 | 1 | 1 |
| `87a88e9b-c744-4c98-8f2b-1da5e2183340` | 2025-05-11 | 3 | 1 |
| `4e459783-e52a-4600-b53f-76c45fc3cdc4` | 2025-05-14 | 2 | 2 |
| `6f47dc77-0e41-4a28-87cd-bc9e8a32e958` | 2025-05-15 | 3 | 0 |
| `077a027a-f296-4784-9f94-a325f8b646dd` | 2025-05-17 | 3 | 1 |
| `7914a47d-f7cd-4e96-b5fc-b9dbae7175dc` | 2025-05-17 | 2 | 1 |
| `7b3c3f89-c5da-4a0b-8040-3709f07d25c3` | 2025-05-18 | 4 | 3 |
| `f5885703-3bb2-4a2a-93cb-c072eb7b9d94` | 2025-05-18 | 4 | 2 |
| `601a7a79-f536-4058-bdfc-02b148347501` | 2025-05-21 | 2 | 1 |
| `1c9e15d7-6405-4aae-b387-99bdad642cb6` | 2025-05-23 | 1 | 0 |
| `4ffe4f10-3379-4e50-978f-e4e1ba78cde4` | 2025-05-24 | 1 | 1 |
| `703e594d-049d-495c-98f1-d56b9699b5e2` | 2025-05-24 | 3 | 2 |
| `7d260fe7-6cbe-4750-b7ab-60f862cb8bcc` | 2025-05-25 | 4 | 3 |
| `95cb4227-f5b7-44d5-9368-2c42586b6d79` | 2025-05-25 | 3 | 1 |
| `acd30c20-2ee4-46d1-8720-3f9f95b9dc85` | 2025-05-25 | 4 | 1 |
| `90a1a43d-5526-49a2-9c7a-5f79825f70ba` | 2025-05-27 | 2 | 1 |
| `17a5495a-8983-449c-b2d6-d1fc87c89489` | 2025-05-28 | 3 | 3 |
| `27325678-5b01-4a13-8254-93a4fdf71cad` | 2025-05-29 | 3 | 2 |
| `ffae764f-c426-4e35-9b18-b195598a2d41` | 2025-05-29 | 4 | 1 |
| `e1ae3e43-74c4-4a4d-a978-75ce82550af7` | 2025-05-30 | 1 | 1 |
| `373a803b-596b-429e-b27f-8bb272fa0e70` | 2025-05-31 | 1 | 0 |
| `e7201d3e-fb69-4dc7-8f82-868050c612f1` | 2025-05-31 | 4 | 2 |
| `4f368d04-ee78-4400-b8e8-45ae48b8b345` | 2025-06-01 | 4 | 1 |
| `a9452686-326b-41ea-a567-58bdf9552287` | 2025-06-01 | 4 | 3 |
| `37883b18-d42d-4b0a-a2e4-44fbac8233c9` | 2025-06-07 | 3 | 0 |
| `e0b95549-522c-4df5-9c47-108854c59f0e` | 2025-06-07 | 3 | 1 |
| `0d8acfd0-5a41-474b-bf51-2ff2a2dc75b9` | 2025-06-08 | 3 | 1 |
| `1b893d1d-c31d-4b95-a2e7-176e17e7bdde` | 2025-06-08 | 3 | 2 |
| `40716575-284a-40f5-8de0-a7317ffd9913` | 2025-06-08 | 4 | 2 |
| `492b3719-01c6-45d2-9444-1c6e2af41994` | 2025-06-10 | 4 | 1 |
| `aa114bc8-2071-45d9-aeed-9357937499e5` | 2025-06-10 | 1 | 1 |
| `311fd64a-b3a4-4033-897b-f74e2bb62e87` | 2025-06-12 | 3 | 2 |
| `5db6c410-2e37-4c5b-a83e-929b75d36998` | 2025-06-13 | 3 | 2 |
| `9bba250f-3123-4154-96da-c40d288e4603` | 2025-06-13 | 4 | 0 |
| `a6b45809-0b67-41eb-ac20-f03ffbdc1f1c` | 2025-06-13 | 3 | 1 |
| `3b945477-27d6-41cd-ad0c-c4599f036f07` | 2025-06-14 | 3 | 0 |
| `6bfac025-58e1-432b-9eb6-906b92324a91` | 2025-06-14 | 2 | 1 |
| `b4913330-5c4c-4efe-be85-bc37f1407d3b` | 2025-06-15 | 3 | 1 |
| `34c07055-2653-4baa-9b68-9a451fd97052` | 2025-06-21 | 3 | 0 |
| `446a5153-f9e7-4fbf-be52-b157e4d41de4` | 2025-06-21 | 3 | 2 |
| `6c2586df-8658-4f11-bb79-e208cd15c563` | 2025-06-22 | 4 | 1 |
| `ee8b48b2-24f6-4fde-8ab5-9a39958e2848` | 2025-06-22 | 3 | 2 |
| `5b182ab0-aa12-44b7-8807-a464232474f0` | 2025-06-25 | 3 | 1 |
| `49d13d90-3831-41cb-8def-da0162a77e67` | 2025-06-27 | 2 | 1 |
| `870581ed-725c-4d31-99ca-2eabbad1101e` | 2025-06-27 | 4 | 1 |
| `8e4ed2d2-2271-441e-8304-9cc7b166cc62` | 2025-06-28 | 3 | 1 |
| `d932e5e8-d20c-4f7d-bc36-c77cca56e749` | 2025-06-28 | 3 | 1 |
| `63e53e8e-22df-460b-98e0-a5a9b0e77849` | 2025-06-29 | 3 | 2 |
| `06852f3e-6626-40a2-bd17-7f18a92cb936` | 2025-07-05 | 3 | 1 |
| `c5cb55c7-d8a5-4dab-90f9-3a117bdcbc55` | 2025-07-05 | 4 | 2 |
| `63d14139-686a-4a50-8f3e-1de4eea67b80` | 2025-07-06 | 3 | 2 |
| `6a5260f1-569f-4adf-9876-b3f951ce2aef` | 2025-07-07 | 2 | 0 |
| `bd1f8d2c-fc33-4dfb-b936-f960567c9502` | 2025-07-07 | 5 | 2 |
| `264c7b15-f1f7-421a-abd3-a4eec7e02eae` | 2025-07-12 | 3 | 1 |
| `86199e44-b708-4778-9b89-6e91d74ab9c8` | 2025-07-12 | 3 | 2 |
| `67537faf-8d25-4aa5-86a5-6db8ae7a0e8f` | 2025-07-13 | 3 | 3 |
| `0373a710-7214-47cf-920c-ca73949ee929` | 2025-07-14 | 2 | 0 |
| `1e0f8dfc-a7cb-46ce-9d3e-671e9110ece6` | 2025-07-15 | 3 | 0 |
| `e5faf695-d9b4-4e83-9de0-edc36cf9d1b7` | 2025-07-15 | 1 | 1 |

**Sample plays:**

| Game | Order | Inn | Half | Outcome | Pitches | QAB |
|------|-------|-----|------|---------|---------|-----|
| `0373a710-7214-47cf-920c-ca73949ee929` | 14 | 2 | top | Fly Out | 4 | 0 |
| `0373a710-7214-47cf-920c-ca73949ee929` | 46 | 5 | top | Fly Out | 3 | 0 |
| `06715ac5-4d35-4c96-a945-d9593f63c68f` | 11 | 2 | top | Ground Out | 5 | 0 |
| `06715ac5-4d35-4c96-a945-d9593f63c68f` | 29 | 4 | top | Walk | 5 | 1 |
| `06715ac5-4d35-4c96-a945-d9593f63c68f` | 46 | 6 | top | Double | 1 | 1 |

#### Owen Hemmingsen (Lincoln Rebels 14U)
Derived=93, GC=99, Diff=6 (6.1%)

**Per-game breakdown:**

| Game | Date | PAs | QAB Count |
|------|------|-----|-----------|
| `990ea59c-ef58-44f9-9da0-7980c1c66bdf` | 2025-04-02 | 3 | 2 |
| `3d31ce33-6983-4c4b-9e25-c0c1cfb0c27f` | 2025-04-04 | 3 | 2 |
| `7ff3818e-2537-472d-b53d-9bd5b15d9894` | 2025-04-05 | 3 | 2 |
| `9014514d-b923-4536-8b30-72029dd059a8` | 2025-04-05 | 4 | 2 |
| `d48ba0c2-4231-4fd6-830a-41e0ea1e32c3` | 2025-04-05 | 3 | 1 |
| `0b8d88cc-01fd-4077-b76d-f13022c271d2` | 2025-04-06 | 4 | 2 |
| `e3471c3b-8c6d-450c-9541-dd20107e9ace` | 2025-04-06 | 4 | 2 |
| `69ca1ed9-f933-407b-937f-d710f4d81c2d` | 2025-04-08 | 3 | 2 |
| `5fc0e97c-bd3f-4e04-b31e-c30ef2593edf` | 2025-04-11 | 3 | 1 |
| `0bf3b9e3-3414-4961-b19b-d58dd82f84d4` | 2025-04-12 | 3 | 1 |
| `44dcf07d-e039-4a1b-a410-f3c9861c500e` | 2025-04-12 | 4 | 2 |
| `ae709c04-debf-47d9-8fd3-3c327d714ae3` | 2025-04-12 | 4 | 4 |
| `4c91cd0b-33d4-463d-a9a4-181bc42aec9c` | 2025-04-13 | 2 | 0 |
| `c37ddf68-ac19-43c9-b694-27e837713415` | 2025-04-13 | 3 | 0 |
| `3c0d2389-0733-4119-911f-2c7b74872b43` | 2025-04-16 | 3 | 1 |
| `56f2bf82-d40c-45c9-9449-d95a41ee0892` | 2025-04-19 | 3 | 1 |
| `717fd9ea-7dac-478a-bcb9-0e83cf315e67` | 2025-04-20 | 4 | 3 |
| `3dcb2a12-7957-4b3f-9061-687069d0770b` | 2025-04-23 | 3 | 1 |
| `453df5f6-24d2-4ba9-a788-90647f0f4dd3` | 2025-04-26 | 1 | 1 |
| `48c79654-eb57-4ea9-8a55-3f328b57e27e` | 2025-04-26 | 3 | 2 |
| `2514bd4d-ce1b-4871-9af5-268ddf5ba16e` | 2025-04-27 | 3 | 0 |
| `5728a6a4-c477-4307-9684-3533fb958c53` | 2025-04-27 | 3 | 2 |
| `06715ac5-4d35-4c96-a945-d9593f63c68f` | 2025-04-28 | 4 | 1 |
| `3565d52b-7cd6-4400-9823-8d0a08aaa182` | 2025-04-30 | 3 | 1 |
| `adfddd15-0633-4963-abbe-d7d3d8b1448b` | 2025-05-03 | 1 | 0 |
| `fc8f3a88-e437-4d13-bd8b-48edb05108e0` | 2025-05-03 | 3 | 0 |
| `07c39def-7720-49d8-83e7-c08c6055a557` | 2025-05-04 | 3 | 1 |
| `e2e6f43f-8671-4f0e-909d-f1642a7fc127` | 2025-05-04 | 3 | 1 |
| `d225c0bf-4718-4ed9-96ae-2471cc9759a7` | 2025-05-07 | 3 | 1 |
| `24fccda9-110e-4614-be8b-3cc821ba8527` | 2025-05-09 | 4 | 1 |
| `107b43c3-b3b2-406f-8f51-74ad25d5c913` | 2025-05-10 | 2 | 1 |
| `65bb31ba-b635-4ae2-9573-75730cd18ebb` | 2025-05-11 | 1 | 0 |
| `87a88e9b-c744-4c98-8f2b-1da5e2183340` | 2025-05-11 | 3 | 1 |
| `4e459783-e52a-4600-b53f-76c45fc3cdc4` | 2025-05-14 | 2 | 1 |
| `6f47dc77-0e41-4a28-87cd-bc9e8a32e958` | 2025-05-15 | 3 | 1 |
| `077a027a-f296-4784-9f94-a325f8b646dd` | 2025-05-17 | 3 | 2 |
| `7914a47d-f7cd-4e96-b5fc-b9dbae7175dc` | 2025-05-17 | 1 | 1 |
| `7b3c3f89-c5da-4a0b-8040-3709f07d25c3` | 2025-05-18 | 3 | 0 |
| `f5885703-3bb2-4a2a-93cb-c072eb7b9d94` | 2025-05-18 | 3 | 1 |
| `601a7a79-f536-4058-bdfc-02b148347501` | 2025-05-21 | 2 | 1 |
| `4ffe4f10-3379-4e50-978f-e4e1ba78cde4` | 2025-05-24 | 1 | 0 |
| `703e594d-049d-495c-98f1-d56b9699b5e2` | 2025-05-24 | 3 | 0 |
| `7d260fe7-6cbe-4750-b7ab-60f862cb8bcc` | 2025-05-25 | 4 | 1 |
| `95cb4227-f5b7-44d5-9368-2c42586b6d79` | 2025-05-25 | 3 | 2 |
| `acd30c20-2ee4-46d1-8720-3f9f95b9dc85` | 2025-05-25 | 4 | 0 |
| `90a1a43d-5526-49a2-9c7a-5f79825f70ba` | 2025-05-27 | 2 | 1 |
| `17a5495a-8983-449c-b2d6-d1fc87c89489` | 2025-05-28 | 2 | 1 |
| `27325678-5b01-4a13-8254-93a4fdf71cad` | 2025-05-29 | 3 | 1 |
| `ffae764f-c426-4e35-9b18-b195598a2d41` | 2025-05-29 | 3 | 1 |
| `e1ae3e43-74c4-4a4d-a978-75ce82550af7` | 2025-05-30 | 1 | 1 |
| `e7201d3e-fb69-4dc7-8f82-868050c612f1` | 2025-05-31 | 4 | 0 |
| `4f368d04-ee78-4400-b8e8-45ae48b8b345` | 2025-06-01 | 3 | 1 |
| `a9452686-326b-41ea-a567-58bdf9552287` | 2025-06-01 | 4 | 1 |
| `37883b18-d42d-4b0a-a2e4-44fbac8233c9` | 2025-06-07 | 3 | 1 |
| `e0b95549-522c-4df5-9c47-108854c59f0e` | 2025-06-07 | 3 | 1 |
| `0d8acfd0-5a41-474b-bf51-2ff2a2dc75b9` | 2025-06-08 | 3 | 2 |
| `1b893d1d-c31d-4b95-a2e7-176e17e7bdde` | 2025-06-08 | 3 | 1 |
| `40716575-284a-40f5-8de0-a7317ffd9913` | 2025-06-08 | 3 | 0 |
| `492b3719-01c6-45d2-9444-1c6e2af41994` | 2025-06-10 | 3 | 2 |
| `aa114bc8-2071-45d9-aeed-9357937499e5` | 2025-06-10 | 1 | 0 |
| `311fd64a-b3a4-4033-897b-f74e2bb62e87` | 2025-06-12 | 3 | 0 |
| `9bba250f-3123-4154-96da-c40d288e4603` | 2025-06-13 | 2 | 2 |
| `a6b45809-0b67-41eb-ac20-f03ffbdc1f1c` | 2025-06-13 | 3 | 1 |
| `3b945477-27d6-41cd-ad0c-c4599f036f07` | 2025-06-14 | 2 | 0 |
| `b4913330-5c4c-4efe-be85-bc37f1407d3b` | 2025-06-15 | 3 | 2 |
| `34c07055-2653-4baa-9b68-9a451fd97052` | 2025-06-21 | 3 | 2 |
| `446a5153-f9e7-4fbf-be52-b157e4d41de4` | 2025-06-21 | 3 | 2 |
| `6c2586df-8658-4f11-bb79-e208cd15c563` | 2025-06-22 | 4 | 0 |
| `ee8b48b2-24f6-4fde-8ab5-9a39958e2848` | 2025-06-22 | 3 | 3 |
| `5b182ab0-aa12-44b7-8807-a464232474f0` | 2025-06-25 | 3 | 1 |
| `49d13d90-3831-41cb-8def-da0162a77e67` | 2025-06-27 | 4 | 2 |
| `870581ed-725c-4d31-99ca-2eabbad1101e` | 2025-06-27 | 1 | 1 |
| `8e4ed2d2-2271-441e-8304-9cc7b166cc62` | 2025-06-28 | 3 | 2 |
| `d932e5e8-d20c-4f7d-bc36-c77cca56e749` | 2025-06-28 | 3 | 1 |
| `63e53e8e-22df-460b-98e0-a5a9b0e77849` | 2025-06-29 | 3 | 1 |
| `06852f3e-6626-40a2-bd17-7f18a92cb936` | 2025-07-05 | 3 | 0 |
| `c5cb55c7-d8a5-4dab-90f9-3a117bdcbc55` | 2025-07-05 | 3 | 1 |
| `63d14139-686a-4a50-8f3e-1de4eea67b80` | 2025-07-06 | 2 | 1 |
| `6a5260f1-569f-4adf-9876-b3f951ce2aef` | 2025-07-07 | 2 | 0 |
| `bd1f8d2c-fc33-4dfb-b936-f960567c9502` | 2025-07-07 | 4 | 1 |
| `264c7b15-f1f7-421a-abd3-a4eec7e02eae` | 2025-07-12 | 3 | 3 |
| `86199e44-b708-4778-9b89-6e91d74ab9c8` | 2025-07-12 | 2 | 0 |
| `67537faf-8d25-4aa5-86a5-6db8ae7a0e8f` | 2025-07-13 | 2 | 1 |
| `0373a710-7214-47cf-920c-ca73949ee929` | 2025-07-14 | 2 | 0 |
| `1e0f8dfc-a7cb-46ce-9d3e-671e9110ece6` | 2025-07-15 | 3 | 0 |
| `e5faf695-d9b4-4e83-9de0-edc36cf9d1b7` | 2025-07-15 | 1 | 0 |

**Sample plays:**

| Game | Order | Inn | Half | Outcome | Pitches | QAB |
|------|-------|-----|------|---------|---------|-----|
| `0373a710-7214-47cf-920c-ca73949ee929` | 13 | 2 | top | Strikeout | 4 | 0 |
| `0373a710-7214-47cf-920c-ca73949ee929` | 45 | 5 | top | Fly Out | 1 | 0 |
| `06715ac5-4d35-4c96-a945-d9593f63c68f` | 10 | 2 | top | Single | 4 | 0 |
| `06715ac5-4d35-4c96-a945-d9593f63c68f` | 22 | 3 | top | Fly Out | 1 | 0 |
| `06715ac5-4d35-4c96-a945-d9593f63c68f` | 41 | 5 | top | Ground Out | 4 | 0 |

#### Owen Rodocker (Lincoln Rebels 14U)
Derived=118, GC=130, Diff=12 (9.2%)

**Per-game breakdown:**

| Game | Date | PAs | QAB Count |
|------|------|-----|-----------|
| `990ea59c-ef58-44f9-9da0-7980c1c66bdf` | 2025-04-02 | 3 | 1 |
| `9014514d-b923-4536-8b30-72029dd059a8` | 2025-04-05 | 4 | 3 |
| `d48ba0c2-4231-4fd6-830a-41e0ea1e32c3` | 2025-04-05 | 1 | 1 |
| `0b8d88cc-01fd-4077-b76d-f13022c271d2` | 2025-04-06 | 4 | 1 |
| `e3471c3b-8c6d-450c-9541-dd20107e9ace` | 2025-04-06 | 2 | 0 |
| `69ca1ed9-f933-407b-937f-d710f4d81c2d` | 2025-04-08 | 3 | 1 |
| `5fc0e97c-bd3f-4e04-b31e-c30ef2593edf` | 2025-04-11 | 2 | 2 |
| `0bf3b9e3-3414-4961-b19b-d58dd82f84d4` | 2025-04-12 | 3 | 1 |
| `44dcf07d-e039-4a1b-a410-f3c9861c500e` | 2025-04-12 | 4 | 3 |
| `4c91cd0b-33d4-463d-a9a4-181bc42aec9c` | 2025-04-13 | 5 | 3 |
| `c37ddf68-ac19-43c9-b694-27e837713415` | 2025-04-13 | 3 | 1 |
| `3c0d2389-0733-4119-911f-2c7b74872b43` | 2025-04-16 | 3 | 2 |
| `56f2bf82-d40c-45c9-9449-d95a41ee0892` | 2025-04-19 | 3 | 2 |
| `717fd9ea-7dac-478a-bcb9-0e83cf315e67` | 2025-04-20 | 3 | 2 |
| `3dcb2a12-7957-4b3f-9061-687069d0770b` | 2025-04-23 | 3 | 2 |
| `453df5f6-24d2-4ba9-a788-90647f0f4dd3` | 2025-04-26 | 3 | 2 |
| `48c79654-eb57-4ea9-8a55-3f328b57e27e` | 2025-04-26 | 2 | 1 |
| `2514bd4d-ce1b-4871-9af5-268ddf5ba16e` | 2025-04-27 | 3 | 1 |
| `5728a6a4-c477-4307-9684-3533fb958c53` | 2025-04-27 | 1 | 1 |
| `06715ac5-4d35-4c96-a945-d9593f63c68f` | 2025-04-28 | 4 | 3 |
| `3565d52b-7cd6-4400-9823-8d0a08aaa182` | 2025-04-30 | 3 | 3 |
| `adfddd15-0633-4963-abbe-d7d3d8b1448b` | 2025-05-03 | 3 | 2 |
| `fc8f3a88-e437-4d13-bd8b-48edb05108e0` | 2025-05-03 | 3 | 1 |
| `07c39def-7720-49d8-83e7-c08c6055a557` | 2025-05-04 | 3 | 2 |
| `d61d8836-d16e-474d-ac52-c394488deddb` | 2025-05-04 | 4 | 0 |
| `e2e6f43f-8671-4f0e-909d-f1642a7fc127` | 2025-05-04 | 4 | 1 |
| `d225c0bf-4718-4ed9-96ae-2471cc9759a7` | 2025-05-07 | 3 | 0 |
| `24fccda9-110e-4614-be8b-3cc821ba8527` | 2025-05-09 | 4 | 3 |
| `107b43c3-b3b2-406f-8f51-74ad25d5c913` | 2025-05-10 | 3 | 1 |
| `3badec1a-f9dc-4912-8f57-5b668fa2d8e6` | 2025-05-10 | 3 | 1 |
| `65bb31ba-b635-4ae2-9573-75730cd18ebb` | 2025-05-11 | 1 | 0 |
| `87a88e9b-c744-4c98-8f2b-1da5e2183340` | 2025-05-11 | 4 | 2 |
| `4e459783-e52a-4600-b53f-76c45fc3cdc4` | 2025-05-14 | 2 | 1 |
| `6f47dc77-0e41-4a28-87cd-bc9e8a32e958` | 2025-05-15 | 3 | 2 |
| `077a027a-f296-4784-9f94-a325f8b646dd` | 2025-05-17 | 3 | 1 |
| `7914a47d-f7cd-4e96-b5fc-b9dbae7175dc` | 2025-05-17 | 2 | 0 |
| `7b3c3f89-c5da-4a0b-8040-3709f07d25c3` | 2025-05-18 | 4 | 2 |
| `f5885703-3bb2-4a2a-93cb-c072eb7b9d94` | 2025-05-18 | 4 | 2 |
| `601a7a79-f536-4058-bdfc-02b148347501` | 2025-05-21 | 2 | 0 |
| `1c9e15d7-6405-4aae-b387-99bdad642cb6` | 2025-05-23 | 1 | 0 |
| `4ffe4f10-3379-4e50-978f-e4e1ba78cde4` | 2025-05-24 | 3 | 1 |
| `703e594d-049d-495c-98f1-d56b9699b5e2` | 2025-05-24 | 3 | 1 |
| `7d260fe7-6cbe-4750-b7ab-60f862cb8bcc` | 2025-05-25 | 4 | 1 |
| `95cb4227-f5b7-44d5-9368-2c42586b6d79` | 2025-05-25 | 3 | 2 |
| `acd30c20-2ee4-46d1-8720-3f9f95b9dc85` | 2025-05-25 | 4 | 1 |
| `90a1a43d-5526-49a2-9c7a-5f79825f70ba` | 2025-05-27 | 2 | 0 |
| `17a5495a-8983-449c-b2d6-d1fc87c89489` | 2025-05-28 | 2 | 1 |
| `27325678-5b01-4a13-8254-93a4fdf71cad` | 2025-05-29 | 3 | 0 |
| `ffae764f-c426-4e35-9b18-b195598a2d41` | 2025-05-29 | 3 | 3 |
| `e1ae3e43-74c4-4a4d-a978-75ce82550af7` | 2025-05-30 | 1 | 0 |
| `373a803b-596b-429e-b27f-8bb272fa0e70` | 2025-05-31 | 3 | 3 |
| `e7201d3e-fb69-4dc7-8f82-868050c612f1` | 2025-05-31 | 1 | 0 |
| `4f368d04-ee78-4400-b8e8-45ae48b8b345` | 2025-06-01 | 3 | 1 |
| `a9452686-326b-41ea-a567-58bdf9552287` | 2025-06-01 | 4 | 2 |
| `37883b18-d42d-4b0a-a2e4-44fbac8233c9` | 2025-06-07 | 3 | 1 |
| `e0b95549-522c-4df5-9c47-108854c59f0e` | 2025-06-07 | 3 | 2 |
| `0d8acfd0-5a41-474b-bf51-2ff2a2dc75b9` | 2025-06-08 | 3 | 2 |
| `1b893d1d-c31d-4b95-a2e7-176e17e7bdde` | 2025-06-08 | 3 | 2 |
| `40716575-284a-40f5-8de0-a7317ffd9913` | 2025-06-08 | 4 | 0 |
| `aa114bc8-2071-45d9-aeed-9357937499e5` | 2025-06-10 | 3 | 2 |
| `311fd64a-b3a4-4033-897b-f74e2bb62e87` | 2025-06-12 | 3 | 1 |
| `5db6c410-2e37-4c5b-a83e-929b75d36998` | 2025-06-13 | 3 | 0 |
| `9bba250f-3123-4154-96da-c40d288e4603` | 2025-06-13 | 3 | 1 |
| `a6b45809-0b67-41eb-ac20-f03ffbdc1f1c` | 2025-06-13 | 1 | 0 |
| `3b945477-27d6-41cd-ad0c-c4599f036f07` | 2025-06-14 | 3 | 0 |
| `6bfac025-58e1-432b-9eb6-906b92324a91` | 2025-06-14 | 2 | 1 |
| `b4913330-5c4c-4efe-be85-bc37f1407d3b` | 2025-06-15 | 3 | 0 |
| `34c07055-2653-4baa-9b68-9a451fd97052` | 2025-06-21 | 3 | 1 |
| `446a5153-f9e7-4fbf-be52-b157e4d41de4` | 2025-06-21 | 3 | 1 |
| `6c2586df-8658-4f11-bb79-e208cd15c563` | 2025-06-22 | 5 | 1 |
| `ee8b48b2-24f6-4fde-8ab5-9a39958e2848` | 2025-06-22 | 3 | 3 |
| `5b182ab0-aa12-44b7-8807-a464232474f0` | 2025-06-25 | 3 | 2 |
| `49d13d90-3831-41cb-8def-da0162a77e67` | 2025-06-27 | 4 | 4 |
| `870581ed-725c-4d31-99ca-2eabbad1101e` | 2025-06-27 | 4 | 0 |
| `8e4ed2d2-2271-441e-8304-9cc7b166cc62` | 2025-06-28 | 3 | 2 |
| `d932e5e8-d20c-4f7d-bc36-c77cca56e749` | 2025-06-28 | 3 | 1 |
| `63e53e8e-22df-460b-98e0-a5a9b0e77849` | 2025-06-29 | 3 | 2 |
| `06852f3e-6626-40a2-bd17-7f18a92cb936` | 2025-07-05 | 3 | 1 |
| `c5cb55c7-d8a5-4dab-90f9-3a117bdcbc55` | 2025-07-05 | 4 | 3 |
| `63d14139-686a-4a50-8f3e-1de4eea67b80` | 2025-07-06 | 3 | 2 |
| `6a5260f1-569f-4adf-9876-b3f951ce2aef` | 2025-07-07 | 2 | 1 |
| `bd1f8d2c-fc33-4dfb-b936-f960567c9502` | 2025-07-07 | 4 | 2 |
| `264c7b15-f1f7-421a-abd3-a4eec7e02eae` | 2025-07-12 | 3 | 2 |
| `86199e44-b708-4778-9b89-6e91d74ab9c8` | 2025-07-12 | 3 | 2 |
| `67537faf-8d25-4aa5-86a5-6db8ae7a0e8f` | 2025-07-13 | 2 | 2 |
| `0373a710-7214-47cf-920c-ca73949ee929` | 2025-07-14 | 2 | 1 |
| `1e0f8dfc-a7cb-46ce-9d3e-671e9110ece6` | 2025-07-15 | 2 | 0 |
| `e5faf695-d9b4-4e83-9de0-edc36cf9d1b7` | 2025-07-15 | 2 | 0 |

**Sample plays:**

| Game | Order | Inn | Half | Outcome | Pitches | QAB |
|------|-------|-----|------|---------|---------|-----|
| `0373a710-7214-47cf-920c-ca73949ee929` | 12 | 2 | top | Walk | 5 | 1 |
| `0373a710-7214-47cf-920c-ca73949ee929` | 39 | 4 | top | Line Out | 1 | 0 |
| `06715ac5-4d35-4c96-a945-d9593f63c68f` | 8 | 2 | top | Walk | 8 | 1 |
| `06715ac5-4d35-4c96-a945-d9593f63c68f` | 20 | 3 | top | Walk | 5 | 1 |
| `06715ac5-4d35-4c96-a945-d9593f63c68f` | 39 | 5 | top | Ground Out | 4 | 0 |

#### Reid Wilkinson (Lincoln Rebels 14U)
Derived=80, GC=85, Diff=5 (5.9%)

**Per-game breakdown:**

| Game | Date | PAs | QAB Count |
|------|------|-----|-----------|
| `990ea59c-ef58-44f9-9da0-7980c1c66bdf` | 2025-04-02 | 3 | 2 |
| `3d31ce33-6983-4c4b-9e25-c0c1cfb0c27f` | 2025-04-04 | 4 | 3 |
| `7ff3818e-2537-472d-b53d-9bd5b15d9894` | 2025-04-05 | 2 | 1 |
| `9014514d-b923-4536-8b30-72029dd059a8` | 2025-04-05 | 4 | 3 |
| `d48ba0c2-4231-4fd6-830a-41e0ea1e32c3` | 2025-04-05 | 3 | 1 |
| `0b8d88cc-01fd-4077-b76d-f13022c271d2` | 2025-04-06 | 3 | 0 |
| `e3471c3b-8c6d-450c-9541-dd20107e9ace` | 2025-04-06 | 2 | 1 |
| `69ca1ed9-f933-407b-937f-d710f4d81c2d` | 2025-04-08 | 3 | 0 |
| `5fc0e97c-bd3f-4e04-b31e-c30ef2593edf` | 2025-04-11 | 4 | 2 |
| `0bf3b9e3-3414-4961-b19b-d58dd82f84d4` | 2025-04-12 | 2 | 1 |
| `ae709c04-debf-47d9-8fd3-3c327d714ae3` | 2025-04-12 | 3 | 1 |
| `4c91cd0b-33d4-463d-a9a4-181bc42aec9c` | 2025-04-13 | 5 | 3 |
| `c37ddf68-ac19-43c9-b694-27e837713415` | 2025-04-13 | 1 | 1 |
| `3c0d2389-0733-4119-911f-2c7b74872b43` | 2025-04-16 | 2 | 1 |
| `56f2bf82-d40c-45c9-9449-d95a41ee0892` | 2025-04-19 | 1 | 0 |
| `717fd9ea-7dac-478a-bcb9-0e83cf315e67` | 2025-04-20 | 3 | 0 |
| `3dcb2a12-7957-4b3f-9061-687069d0770b` | 2025-04-23 | 3 | 3 |
| `453df5f6-24d2-4ba9-a788-90647f0f4dd3` | 2025-04-26 | 3 | 1 |
| `48c79654-eb57-4ea9-8a55-3f328b57e27e` | 2025-04-26 | 3 | 3 |
| `2514bd4d-ce1b-4871-9af5-268ddf5ba16e` | 2025-04-27 | 1 | 1 |
| `5728a6a4-c477-4307-9684-3533fb958c53` | 2025-04-27 | 2 | 1 |
| `06715ac5-4d35-4c96-a945-d9593f63c68f` | 2025-04-28 | 4 | 1 |
| `3565d52b-7cd6-4400-9823-8d0a08aaa182` | 2025-04-30 | 2 | 0 |
| `adfddd15-0633-4963-abbe-d7d3d8b1448b` | 2025-05-03 | 3 | 1 |
| `fc8f3a88-e437-4d13-bd8b-48edb05108e0` | 2025-05-03 | 4 | 3 |
| `d61d8836-d16e-474d-ac52-c394488deddb` | 2025-05-04 | 4 | 0 |
| `e2e6f43f-8671-4f0e-909d-f1642a7fc127` | 2025-05-04 | 2 | 2 |
| `d225c0bf-4718-4ed9-96ae-2471cc9759a7` | 2025-05-07 | 3 | 0 |
| `24fccda9-110e-4614-be8b-3cc821ba8527` | 2025-05-09 | 4 | 2 |
| `3badec1a-f9dc-4912-8f57-5b668fa2d8e6` | 2025-05-10 | 2 | 2 |
| `65bb31ba-b635-4ae2-9573-75730cd18ebb` | 2025-05-11 | 1 | 0 |
| `87a88e9b-c744-4c98-8f2b-1da5e2183340` | 2025-05-11 | 1 | 0 |
| `4e459783-e52a-4600-b53f-76c45fc3cdc4` | 2025-05-14 | 3 | 1 |
| `6f47dc77-0e41-4a28-87cd-bc9e8a32e958` | 2025-05-15 | 3 | 2 |
| `077a027a-f296-4784-9f94-a325f8b646dd` | 2025-05-17 | 3 | 0 |
| `7914a47d-f7cd-4e96-b5fc-b9dbae7175dc` | 2025-05-17 | 1 | 0 |
| `7b3c3f89-c5da-4a0b-8040-3709f07d25c3` | 2025-05-18 | 3 | 0 |
| `f5885703-3bb2-4a2a-93cb-c072eb7b9d94` | 2025-05-18 | 3 | 1 |
| `601a7a79-f536-4058-bdfc-02b148347501` | 2025-05-21 | 2 | 1 |
| `1c9e15d7-6405-4aae-b387-99bdad642cb6` | 2025-05-23 | 4 | 1 |
| `4ffe4f10-3379-4e50-978f-e4e1ba78cde4` | 2025-05-24 | 3 | 2 |
| `703e594d-049d-495c-98f1-d56b9699b5e2` | 2025-05-24 | 2 | 1 |
| `7d260fe7-6cbe-4750-b7ab-60f862cb8bcc` | 2025-05-25 | 4 | 1 |
| `95cb4227-f5b7-44d5-9368-2c42586b6d79` | 2025-05-25 | 3 | 1 |
| `90a1a43d-5526-49a2-9c7a-5f79825f70ba` | 2025-05-27 | 1 | 1 |
| `17a5495a-8983-449c-b2d6-d1fc87c89489` | 2025-05-28 | 2 | 0 |
| `27325678-5b01-4a13-8254-93a4fdf71cad` | 2025-05-29 | 2 | 0 |
| `e1ae3e43-74c4-4a4d-a978-75ce82550af7` | 2025-05-30 | 2 | 1 |
| `373a803b-596b-429e-b27f-8bb272fa0e70` | 2025-05-31 | 3 | 0 |
| `e7201d3e-fb69-4dc7-8f82-868050c612f1` | 2025-05-31 | 3 | 3 |
| `4f368d04-ee78-4400-b8e8-45ae48b8b345` | 2025-06-01 | 2 | 0 |
| `a9452686-326b-41ea-a567-58bdf9552287` | 2025-06-01 | 1 | 1 |
| `e0b95549-522c-4df5-9c47-108854c59f0e` | 2025-06-07 | 2 | 1 |
| `40716575-284a-40f5-8de0-a7317ffd9913` | 2025-06-08 | 2 | 1 |
| `492b3719-01c6-45d2-9444-1c6e2af41994` | 2025-06-10 | 4 | 2 |
| `aa114bc8-2071-45d9-aeed-9357937499e5` | 2025-06-10 | 4 | 1 |
| `311fd64a-b3a4-4033-897b-f74e2bb62e87` | 2025-06-12 | 4 | 1 |
| `9bba250f-3123-4154-96da-c40d288e4603` | 2025-06-13 | 2 | 1 |
| `a6b45809-0b67-41eb-ac20-f03ffbdc1f1c` | 2025-06-13 | 3 | 1 |
| `3b945477-27d6-41cd-ad0c-c4599f036f07` | 2025-06-14 | 3 | 1 |
| `b4913330-5c4c-4efe-be85-bc37f1407d3b` | 2025-06-15 | 1 | 0 |
| `ee8b48b2-24f6-4fde-8ab5-9a39958e2848` | 2025-06-22 | 2 | 2 |
| `49d13d90-3831-41cb-8def-da0162a77e67` | 2025-06-27 | 1 | 0 |
| `870581ed-725c-4d31-99ca-2eabbad1101e` | 2025-06-27 | 3 | 2 |
| `8e4ed2d2-2271-441e-8304-9cc7b166cc62` | 2025-06-28 | 1 | 1 |
| `d932e5e8-d20c-4f7d-bc36-c77cca56e749` | 2025-06-28 | 3 | 0 |
| `06852f3e-6626-40a2-bd17-7f18a92cb936` | 2025-07-05 | 2 | 1 |
| `c5cb55c7-d8a5-4dab-90f9-3a117bdcbc55` | 2025-07-05 | 1 | 0 |
| `63d14139-686a-4a50-8f3e-1de4eea67b80` | 2025-07-06 | 2 | 1 |
| `bd1f8d2c-fc33-4dfb-b936-f960567c9502` | 2025-07-07 | 4 | 3 |
| `264c7b15-f1f7-421a-abd3-a4eec7e02eae` | 2025-07-12 | 2 | 2 |
| `86199e44-b708-4778-9b89-6e91d74ab9c8` | 2025-07-12 | 2 | 0 |
| `67537faf-8d25-4aa5-86a5-6db8ae7a0e8f` | 2025-07-13 | 2 | 0 |
| `0373a710-7214-47cf-920c-ca73949ee929` | 2025-07-14 | 2 | 0 |
| `1e0f8dfc-a7cb-46ce-9d3e-671e9110ece6` | 2025-07-15 | 3 | 1 |
| `e5faf695-d9b4-4e83-9de0-edc36cf9d1b7` | 2025-07-15 | 1 | 1 |

**Sample plays:**

| Game | Order | Inn | Half | Outcome | Pitches | QAB |
|------|-------|-----|------|---------|---------|-----|
| `0373a710-7214-47cf-920c-ca73949ee929` | 3 | 1 | top | Strikeout | 4 | 0 |
| `0373a710-7214-47cf-920c-ca73949ee929` | 29 | 3 | top | Ground Out | 4 | 0 |
| `06715ac5-4d35-4c96-a945-d9593f63c68f` | 12 | 2 | top | Dropped 3rd Strike | 5 | 0 |
| `06715ac5-4d35-4c96-a945-d9593f63c68f` | 30 | 4 | top | Strikeout | 4 | 0 |
| `06715ac5-4d35-4c96-a945-d9593f63c68f` | 47 | 6 | top | Walk | 4 | 1 |

#### Tanner Rahmatulla (Standing Bear Freshman Grizzlies)
Derived=16, GC=17, Diff=1 (5.9%)

**Per-game breakdown:**

| Game | Date | PAs | QAB Count |
|------|------|-----|-----------|
| `91d00308-a64a-4738-bb7a-7f5be266e1c1` | 2026-03-19 | 4 | 2 |
| `155bc5ef-3347-4b23-b4ed-4ea8f1e3e9c7` | 2026-03-20 | 3 | 1 |
| `757c024c-de8d-4b44-b159-7704a6ff0640` | 2026-03-21 | 4 | 3 |
| `374ca73f-342c-4f24-a5ca-af155e09e9d9` | 2026-03-25 | 4 | 1 |
| `a31f3884-456d-484b-a5c8-8df3333e3de7` | 2026-03-26 | 4 | 3 |
| `903c7d39-ea42-4669-a621-9756be5fd8b1` | 2026-03-28 | 1 | 0 |
| `cd30b1e3-85f8-4283-9249-47ad013a1f04` | 2026-03-28 | 3 | 3 |
| `72e91b67-2d01-4821-9a63-9c7958a5afe9` | 2026-03-30 | 5 | 3 |
| `2975658b-9608-4176-a3df-69aa45d00af3` | 2026-04-01 | 4 | 0 |

**Sample plays:**

| Game | Order | Inn | Half | Outcome | Pitches | QAB |
|------|-------|-----|------|---------|---------|-----|
| `155bc5ef-3347-4b23-b4ed-4ea8f1e3e9c7` | 6 | 1 | bottom | Ground Out | 2 | 0 |
| `155bc5ef-3347-4b23-b4ed-4ea8f1e3e9c7` | 26 | 2 | bottom | Walk | 5 | 1 |
| `155bc5ef-3347-4b23-b4ed-4ea8f1e3e9c7` | 48 | 3 | bottom | Single | 4 | 0 |
| `2975658b-9608-4176-a3df-69aa45d00af3` | 4 | 1 | bottom | Strikeout | 3 | 0 |
| `2975658b-9608-4176-a3df-69aa45d00af3` | 26 | 3 | bottom | Single | 3 | 0 |

#### Truman Jackson (Lincoln Rebels 14U)
Derived=122, GC=132, Diff=10 (7.6%)

**Per-game breakdown:**

| Game | Date | PAs | QAB Count |
|------|------|-----|-----------|
| `990ea59c-ef58-44f9-9da0-7980c1c66bdf` | 2025-04-02 | 3 | 1 |
| `3d31ce33-6983-4c4b-9e25-c0c1cfb0c27f` | 2025-04-04 | 3 | 0 |
| `7ff3818e-2537-472d-b53d-9bd5b15d9894` | 2025-04-05 | 3 | 1 |
| `0b8d88cc-01fd-4077-b76d-f13022c271d2` | 2025-04-06 | 4 | 1 |
| `e3471c3b-8c6d-450c-9541-dd20107e9ace` | 2025-04-06 | 4 | 1 |
| `69ca1ed9-f933-407b-937f-d710f4d81c2d` | 2025-04-08 | 3 | 1 |
| `5fc0e97c-bd3f-4e04-b31e-c30ef2593edf` | 2025-04-11 | 3 | 2 |
| `0bf3b9e3-3414-4961-b19b-d58dd82f84d4` | 2025-04-12 | 2 | 2 |
| `44dcf07d-e039-4a1b-a410-f3c9861c500e` | 2025-04-12 | 4 | 1 |
| `ae709c04-debf-47d9-8fd3-3c327d714ae3` | 2025-04-12 | 4 | 2 |
| `4c91cd0b-33d4-463d-a9a4-181bc42aec9c` | 2025-04-13 | 5 | 3 |
| `c37ddf68-ac19-43c9-b694-27e837713415` | 2025-04-13 | 4 | 2 |
| `3c0d2389-0733-4119-911f-2c7b74872b43` | 2025-04-16 | 2 | 2 |
| `56f2bf82-d40c-45c9-9449-d95a41ee0892` | 2025-04-19 | 3 | 1 |
| `717fd9ea-7dac-478a-bcb9-0e83cf315e67` | 2025-04-20 | 4 | 1 |
| `3dcb2a12-7957-4b3f-9061-687069d0770b` | 2025-04-23 | 3 | 0 |
| `48c79654-eb57-4ea9-8a55-3f328b57e27e` | 2025-04-26 | 3 | 1 |
| `2514bd4d-ce1b-4871-9af5-268ddf5ba16e` | 2025-04-27 | 3 | 1 |
| `5728a6a4-c477-4307-9684-3533fb958c53` | 2025-04-27 | 3 | 2 |
| `06715ac5-4d35-4c96-a945-d9593f63c68f` | 2025-04-28 | 4 | 1 |
| `3565d52b-7cd6-4400-9823-8d0a08aaa182` | 2025-04-30 | 2 | 1 |
| `adfddd15-0633-4963-abbe-d7d3d8b1448b` | 2025-05-03 | 3 | 2 |
| `fc8f3a88-e437-4d13-bd8b-48edb05108e0` | 2025-05-03 | 3 | 2 |
| `07c39def-7720-49d8-83e7-c08c6055a557` | 2025-05-04 | 3 | 0 |
| `d61d8836-d16e-474d-ac52-c394488deddb` | 2025-05-04 | 4 | 3 |
| `e2e6f43f-8671-4f0e-909d-f1642a7fc127` | 2025-05-04 | 4 | 1 |
| `d225c0bf-4718-4ed9-96ae-2471cc9759a7` | 2025-05-07 | 3 | 1 |
| `107b43c3-b3b2-406f-8f51-74ad25d5c913` | 2025-05-10 | 3 | 2 |
| `3badec1a-f9dc-4912-8f57-5b668fa2d8e6` | 2025-05-10 | 3 | 1 |
| `65bb31ba-b635-4ae2-9573-75730cd18ebb` | 2025-05-11 | 2 | 1 |
| `87a88e9b-c744-4c98-8f2b-1da5e2183340` | 2025-05-11 | 4 | 3 |
| `4e459783-e52a-4600-b53f-76c45fc3cdc4` | 2025-05-14 | 2 | 1 |
| `6f47dc77-0e41-4a28-87cd-bc9e8a32e958` | 2025-05-15 | 3 | 1 |
| `077a027a-f296-4784-9f94-a325f8b646dd` | 2025-05-17 | 3 | 0 |
| `7914a47d-f7cd-4e96-b5fc-b9dbae7175dc` | 2025-05-17 | 2 | 0 |
| `7b3c3f89-c5da-4a0b-8040-3709f07d25c3` | 2025-05-18 | 4 | 2 |
| `f5885703-3bb2-4a2a-93cb-c072eb7b9d94` | 2025-05-18 | 4 | 1 |
| `601a7a79-f536-4058-bdfc-02b148347501` | 2025-05-21 | 2 | 0 |
| `1c9e15d7-6405-4aae-b387-99bdad642cb6` | 2025-05-23 | 3 | 1 |
| `4ffe4f10-3379-4e50-978f-e4e1ba78cde4` | 2025-05-24 | 3 | 2 |
| `703e594d-049d-495c-98f1-d56b9699b5e2` | 2025-05-24 | 2 | 1 |
| `7d260fe7-6cbe-4750-b7ab-60f862cb8bcc` | 2025-05-25 | 4 | 3 |
| `95cb4227-f5b7-44d5-9368-2c42586b6d79` | 2025-05-25 | 3 | 3 |
| `acd30c20-2ee4-46d1-8720-3f9f95b9dc85` | 2025-05-25 | 4 | 4 |
| `90a1a43d-5526-49a2-9c7a-5f79825f70ba` | 2025-05-27 | 2 | 1 |
| `17a5495a-8983-449c-b2d6-d1fc87c89489` | 2025-05-28 | 3 | 1 |
| `27325678-5b01-4a13-8254-93a4fdf71cad` | 2025-05-29 | 3 | 1 |
| `ffae764f-c426-4e35-9b18-b195598a2d41` | 2025-05-29 | 4 | 2 |
| `e1ae3e43-74c4-4a4d-a978-75ce82550af7` | 2025-05-30 | 4 | 2 |
| `373a803b-596b-429e-b27f-8bb272fa0e70` | 2025-05-31 | 1 | 0 |
| `e7201d3e-fb69-4dc7-8f82-868050c612f1` | 2025-05-31 | 4 | 2 |
| `4f368d04-ee78-4400-b8e8-45ae48b8b345` | 2025-06-01 | 3 | 0 |
| `a9452686-326b-41ea-a567-58bdf9552287` | 2025-06-01 | 4 | 3 |
| `37883b18-d42d-4b0a-a2e4-44fbac8233c9` | 2025-06-07 | 3 | 3 |
| `e0b95549-522c-4df5-9c47-108854c59f0e` | 2025-06-07 | 3 | 2 |
| `0d8acfd0-5a41-474b-bf51-2ff2a2dc75b9` | 2025-06-08 | 3 | 2 |
| `1b893d1d-c31d-4b95-a2e7-176e17e7bdde` | 2025-06-08 | 3 | 2 |
| `40716575-284a-40f5-8de0-a7317ffd9913` | 2025-06-08 | 4 | 0 |
| `492b3719-01c6-45d2-9444-1c6e2af41994` | 2025-06-10 | 4 | 2 |
| `aa114bc8-2071-45d9-aeed-9357937499e5` | 2025-06-10 | 1 | 0 |
| `311fd64a-b3a4-4033-897b-f74e2bb62e87` | 2025-06-12 | 1 | 0 |
| `5db6c410-2e37-4c5b-a83e-929b75d36998` | 2025-06-13 | 3 | 1 |
| `9bba250f-3123-4154-96da-c40d288e4603` | 2025-06-13 | 3 | 2 |
| `a6b45809-0b67-41eb-ac20-f03ffbdc1f1c` | 2025-06-13 | 3 | 1 |
| `3b945477-27d6-41cd-ad0c-c4599f036f07` | 2025-06-14 | 2 | 0 |
| `6bfac025-58e1-432b-9eb6-906b92324a91` | 2025-06-14 | 2 | 1 |
| `b4913330-5c4c-4efe-be85-bc37f1407d3b` | 2025-06-15 | 3 | 0 |
| `34c07055-2653-4baa-9b68-9a451fd97052` | 2025-06-21 | 3 | 3 |
| `446a5153-f9e7-4fbf-be52-b157e4d41de4` | 2025-06-21 | 4 | 2 |
| `6c2586df-8658-4f11-bb79-e208cd15c563` | 2025-06-22 | 5 | 4 |
| `ee8b48b2-24f6-4fde-8ab5-9a39958e2848` | 2025-06-22 | 3 | 1 |
| `5b182ab0-aa12-44b7-8807-a464232474f0` | 2025-06-25 | 3 | 1 |
| `49d13d90-3831-41cb-8def-da0162a77e67` | 2025-06-27 | 4 | 0 |
| `870581ed-725c-4d31-99ca-2eabbad1101e` | 2025-06-27 | 4 | 2 |
| `8e4ed2d2-2271-441e-8304-9cc7b166cc62` | 2025-06-28 | 3 | 1 |
| `d932e5e8-d20c-4f7d-bc36-c77cca56e749` | 2025-06-28 | 3 | 1 |
| `63e53e8e-22df-460b-98e0-a5a9b0e77849` | 2025-06-29 | 3 | 1 |
| `06852f3e-6626-40a2-bd17-7f18a92cb936` | 2025-07-05 | 3 | 2 |
| `c5cb55c7-d8a5-4dab-90f9-3a117bdcbc55` | 2025-07-05 | 4 | 2 |
| `63d14139-686a-4a50-8f3e-1de4eea67b80` | 2025-07-06 | 3 | 2 |
| `6a5260f1-569f-4adf-9876-b3f951ce2aef` | 2025-07-07 | 2 | 0 |
| `bd1f8d2c-fc33-4dfb-b936-f960567c9502` | 2025-07-07 | 5 | 1 |
| `264c7b15-f1f7-421a-abd3-a4eec7e02eae` | 2025-07-12 | 3 | 2 |
| `86199e44-b708-4778-9b89-6e91d74ab9c8` | 2025-07-12 | 3 | 3 |
| `67537faf-8d25-4aa5-86a5-6db8ae7a0e8f` | 2025-07-13 | 3 | 2 |
| `0373a710-7214-47cf-920c-ca73949ee929` | 2025-07-14 | 2 | 0 |
| `1e0f8dfc-a7cb-46ce-9d3e-671e9110ece6` | 2025-07-15 | 3 | 2 |
| `e5faf695-d9b4-4e83-9de0-edc36cf9d1b7` | 2025-07-15 | 2 | 0 |

**Sample plays:**

| Game | Order | Inn | Half | Outcome | Pitches | QAB |
|------|-------|-----|------|---------|---------|-----|
| `0373a710-7214-47cf-920c-ca73949ee929` | 16 | 2 | top | Fielder's Choice | 2 | 0 |
| `0373a710-7214-47cf-920c-ca73949ee929` | 48 | 5 | top | Pop Out | 1 | 0 |
| `06715ac5-4d35-4c96-a945-d9593f63c68f` | 1 | 1 | top | Fly Out | 1 | 0 |
| `06715ac5-4d35-4c96-a945-d9593f63c68f` | 18 | 3 | top | Ground Out | 2 | 0 |
| `06715ac5-4d35-4c96-a945-d9593f63c68f` | 33 | 4 | top | Strikeout | 6 | 1 |

## Summary

- FPS match rate: **55.6%**
- QAB match rate: **53.8%**
- Plays coverage: **101/101** completed games
- FPS outliers (>5.0%): **12**
- QAB outliers (>5.0%): **12**
