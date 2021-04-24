dir_src = src
dir_docs = docs
dir_docs_html = $(dir_docs)/html
src_files = $(shell find $(dir_src) -type f)
app_pdoc = pdoc3

all: docs

docs: $(src_files)
	PYTHONDONTWRITEBYTECODE=1 $(app_pdoc) --html -o $(dir_docs_html) $(src_files) --force 

clean:
	rm -f $(dir_docs)/*

