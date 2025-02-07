verify:
	cd interface && make verify
	cd impl && make verify

check-untracked:
	if [ ! -z "$$(git diff --name-only -- nora_lib-impl/src)" ] ; then echo "Some files in src are not checked in" ; exit 1 ; fi

publish: check-untracked verify
	export NORA_LIB_VERSION=$$(cat version.txt) ; \
	git tag v$$NORA_LIB_VERSION ; \
	git push origin --tags ; \
	cd $(CURDIR)/impl && ../publish.sh ; \
	cd $(CURDIR)/interface && ../publish.sh
