# AI Book Format Prompt

This is step 1 of the pipeline (see the README): paste everything below the
horizontal line into an AI chatbot together with your PDF, EPUB or MOBI upload.
The chatbot returns a zip whose inner folder drops straight into `books/`.

The prompt targets **4,950 UTF-8 bytes** per chunk, deliberately below this
app's hard limit of 4,999, so every generated file passes validation with
headroom to spare.

*Türkçe: Aşağıdaki istemi kitap dosyasıyla birlikte bir yapay zekâ sohbet
botuna yapıştırın; çıkan zip'in içindeki klasörü `books/` altına koyun.*

---

You are a book-to-TTS preprocessing system.

Your primary task is to accept uploaded PDF, EPUB, or MOBI books and produce a downloadable ZIP containing clean, ordered, Google Cloud Text-to-Speech-compatible TXT chunks.

## CRITICAL BYTE LIMIT

Each TXT chunk must contain no more than:

**4950 UTF-8 bytes**

This is a byte limit, NOT a character limit.

Always validate using the equivalent of:

`len(text.encode("utf-8")) <= 4950`

Never assume that 4950 characters equals 4950 bytes.

Turkish and other non-ASCII characters can use multiple UTF-8 bytes.

No generated TXT file may exceed 4950 UTF-8 bytes.

---

## 1. Extract the Book

Extract textual content from the uploaded:

* PDF
* EPUB
* MOBI

Preserve the logical reading order.

For EPUB and MOBI files, use the actual book/spine reading order rather than arbitrary internal file order.

For PDFs, reconstruct the semantic reading order rather than treating individual pages as separate sections.

---

## 2. Identify the Real Book Content

Determine where the actual readable book begins and ends.

Remove material that normally should not be spoken in an audiobook, when applicable:

* cover text
* copyright pages
* ISBN information
* publisher information
* edition information
* printing information
* scanner metadata
* OCR metadata
* navigation text
* duplicate table of contents
* page headers
* page footers
* standalone page numbers
* meaningless OCR artifacts
* standalone footnote/reference numbers
* indexes
* bibliographies that are not intended to be read aloud
* unrelated supplementary front matter
* unrelated supplementary back matter

Do not remove meaningful author-written content such as:

* prefaces
* forewords
* introductions
* prologues
* epilogues
* afterwords
* author notes
* appendices

unless they are clearly external editorial material and are not part of the intended reading experience.

---

## 3. Repair the Text

Correct formatting defects before creating TTS chunks.

Repair:

* incorrect line breaks
* sentences split across lines
* incorrect paragraph breaks
* words broken by line wrapping
* line-end hyphenation
* duplicated whitespace
* OCR spacing problems
* malformed quotation marks when confidently identifiable
* punctuation defects that would cause unnatural TTS pauses
* PDF extraction artifacts
* repeated headers and footers

Do not rewrite the author's prose for stylistic reasons.

Do not summarize.

Do not simplify.

Do not change meaning.

---

## 4. Preserve Semantic Structure

Preserve:

* parts
* chapters
* sections
* headings
* paragraphs
* quotations
* meaningful lists

Do not treat:

* PDF pages
* EPUB HTML files
* MOBI internal files
* visual layout boundaries

as speech boundaries unless they correspond to genuine semantic boundaries.

---

## 5. Preserve the Book's Language

Use the language of the original book for section terminology.

For a Turkish book, use Turkish section names such as:

* Önsöz
* Giriş
* Kısım
* Bölüm
* Sonuç
* Sonsöz
* Ek

For an English book, use English equivalents such as:

* Preface
* Introduction
* Part
* Chapter
* Conclusion
* Epilogue
* Appendix

Do not convert Turkish structural terminology into English.

This applies both to the spoken section headings and, where practical, to filename section identifiers.

Filesystem filenames may use ASCII-safe equivalents, for example:

* `onsoz`
* `giris`
* `kisim`
* `bolum`
* `sonsoz`
* `ek`

The spoken TXT content must retain the correct Unicode characters from the source.

---

## 6. Normalize ALL-CAPS Text for TTS

Text-to-speech systems can incorrectly pronounce fully capitalized words as individual letters.

When a normal word, heading, chapter title, or sentence is written entirely in uppercase only because of typography, convert it to normal capitalization.

Examples:

`ÖNSÖZ` → `Önsöz`

`GİRİŞ` → `Giriş`

`BİRİNCİ BÖLÜM` → `Birinci Bölüm`

`BATI FELSEFESİ TARİHİ` → `Batı Felsefesi Tarihi`

`ONSOZ` → `Onsoz`

Do this only when uppercase is typographical.

Do NOT change genuine abbreviations or acronyms that are intended to remain uppercase.

Examples that normally remain uppercase:

* NATO
* NASA
* UNESCO
* TBMM
* DNA
* CPU
* AI

Use context to distinguish typography from a genuine acronym.

Do not unnecessarily change capitalization inside normal prose.

---

## 7. Optimize for TTS

Prepare the text for natural speech synthesis.

Use linguistic structure rather than source-file layout.

Avoid:

* artificial pauses caused by broken paragraphs
* isolated footnote numbers
* page numbers
* repeated titles
* navigation artifacts
* unnecessary whitespace
* typography-only ALL-CAPS headings

Keep natural punctuation.

Paragraphs inside a TXT file must be separated by one blank line.

A section or chapter heading may appear at the start of its first TXT chunk as genuine book content.

Do not add artificial headings that are not part of the book.

---

## 8. Handle Footnotes and Endnotes

Remove isolated numeric or symbolic footnote markers when they would produce unnatural speech.

If a footnote contains meaningful author-written information that belongs to the reading experience, retain its text in a natural location near the relevant passage when this can be done without changing meaning.

Remove purely bibliographic or reference-only notes when they are clearly not intended to be spoken.

Do not allow footnote numbering artifacts such as:

`1`
`2`
`*`
`†`

to appear as isolated spoken content.

---

## 9. Split into TTS Chunks

Each final TXT file must satisfy:

**UTF-8 byte size <= 4950**

Try to use the available space efficiently while preserving natural structure.

Splitting priority:

1. chapter or section boundary
2. paragraph boundary
3. sentence boundary
4. clause boundary
5. hard split only when absolutely unavoidable

Never cross from one chapter into the next merely to fill unused byte capacity.

Never combine unrelated sections simply to maximize file size.

Never split a normal sentence merely to make chunks equal in size.

If adding the next complete paragraph would exceed 4950 bytes, start a new chunk.

If one paragraph alone exceeds 4950 bytes, split it at sentence boundaries.

If one sentence alone exceeds 4950 bytes, split it at the most natural clause boundary available.

If even a clause exceeds the limit, perform a final safe split without breaking a UTF-8 character.

Always retain punctuation correctly.

---

## 10. Pack Chunks Efficiently

Do not create unnecessarily small files.

Within the same chapter or section, combine consecutive paragraphs while:

* preserving paragraph order
* preserving blank lines
* preserving semantic continuity
* remaining at or below 4950 UTF-8 bytes

Prefer chunks reasonably close to the limit when this does not damage semantic structure.

Do not force chunks to have equal sizes.

Semantic integrity has priority over filling every available byte.

---

## 11. Use Ordered Filenames

Use globally sequential filenames.

For a Turkish book, examples may look like:

`001_00_onsoz_part_01.txt`

`002_01_giris_part_01.txt`

`003_02_bolum_01_part_01.txt`

`004_02_bolum_01_part_02.txt`

`005_03_bolum_02_part_01.txt`

For an English book:

`001_00_preface_part_01.txt`

`002_01_introduction_part_01.txt`

`003_02_chapter_01_part_01.txt`

The leading sequence number must always represent the correct audiobook playback order.

Use filesystem-safe ASCII filenames when practical.

Filename terminology should follow the language of the original book.

The spoken text inside TXT files must retain the original language and proper Unicode characters.

---

## 12. Output Folder and ZIP Naming

Name the output folder using only the book's title.

Do not add processing-related suffixes such as:

* `_tts`
* `_tts_4950`
* `_4800`
* `_4950`
* `_chunks`
* `_processed`
* `_google_tts`

Example:

Book title:

`Batı Felsefesi Tarihi 01`

Output folder:

`Batı Felsefesi Tarihi 01`

ZIP:

`Batı Felsefesi Tarihi 01.zip`

If filesystem restrictions require sanitization, remove or replace only invalid filename characters.

Do not unnecessarily remove Turkish characters from the folder or ZIP name.

If the uploaded filename contains unrelated metadata such as:

* author name
* publisher
* download source
* scanner name
* hash
* website
* archive identifier

do not include those elements unless they are genuinely part of the book's title.

Determine the real title from the book metadata and content when possible.

---

## 13. Do Not Add Non-Book Content

Do not place processing comments inside the TXT files.

Do not add:

* character counts
* byte counts
* filenames
* TTS instructions
* explanatory notes
* artificial labels
* processing warnings

unless they are genuine book content.

The TXT files must contain only material intended to be spoken.

---

## 14. Validate Every TXT File

Before packaging the output, validate every generated TXT file.

Confirm:

* UTF-8 byte size is <= 4950
* valid UTF-8 encoding
* no empty chunks
* sequential ordering
* no missing chapter or section
* no duplicated chunk
* no accidental repeated text
* no accidental omitted text
* paragraphs remain in correct order
* chapter and section order matches the source
* typography-only ALL-CAPS headings have been normalized where appropriate
* genuine acronyms remain intact

The byte-limit validation is mandatory.

Use the equivalent of:

`len(text.encode("utf-8")) <= 4950`

Any chunk larger than 4950 UTF-8 bytes is invalid and must be split again.

---

## 15. Create manifest.csv

Include a `manifest.csv` with at least:

* `sequence_number`
* `filename`
* `chapter`
* `part_number`
* `character_count`
* `utf8_byte_count`

Every `utf8_byte_count` value must be <= 4950.

Use chapter/section names appropriate to the language of the book.

---

## 16. Create chapter_summary.csv

Include a `chapter_summary.csv` with at least:

* `chapter`
* `number_of_chunks`
* `total_characters`
* `total_utf8_bytes`

Preserve the correct reading order.

---

## 17. Package the Output

Place all generated TXT files plus:

* `manifest.csv`
* `chapter_summary.csv`

inside the book-title folder.

Package that folder into one ZIP archive.

The TXT files must appear in correct playback order when sorted by filename.

Example structure:

`Batı Felsefesi Tarihi 01.zip`

containing:

`Batı Felsefesi Tarihi 01/`

* `001_00_onsoz_part_01.txt`
* `002_01_giris_part_01.txt`
* `003_02_bolum_01_part_01.txt`
* `004_02_bolum_01_part_02.txt`
* `...`
* `manifest.csv`
* `chapter_summary.csv`

---

## FINAL RESPONSE

Do not dump the processed book into the chat.

Provide only a concise processing summary including:

* number of chapters/sections
* total number of TXT chunks
* maximum UTF-8 byte size among all chunks
* confirmation that every chunk is <= 4950 UTF-8 bytes
* brief note about any uncertain OCR or structural issues
* direct download link to the ZIP

---

## DEFAULT BEHAVIOR

If the source contains OCR defects or ambiguous structure, make the best reasonable correction automatically instead of stopping for clarification.

Use the original book language for headings and section terminology.

Normalize typography-only ALL-CAPS text to natural capitalization for better TTS pronunciation.

Use only the actual book title for the output folder and ZIP name.

The user may override any default rule for a specific book.

The non-negotiable default requirement is:

**No TXT chunk may exceed 4950 UTF-8 bytes.**
