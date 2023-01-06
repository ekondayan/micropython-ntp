dir_src = src
dir_docs = docs
src_files = $(shell find $(dir_src) -type f)
app_pdoc = pdoc3
chromium_browser = brave-browser

all: html pdf

html: $(src_files)
	PYTHONDONTWRITEBYTECODE=1 $(app_pdoc) --html -o $(dir_docs) $(src_files) --force

pdf: 
	$(chromium_browser) --headless --disable-gpu --print-to-pdf=$(dir_docs)/ntp.pdf $(dir_docs)/ntp.html

clean:
	rm -rf $(dir_docs)

