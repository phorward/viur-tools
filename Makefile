
nothing:
	@echo "Either type 'make install' or 'make uninstall' to set/unset symlinks"

install:
	-ln `pwd`/clean.sh ../clean.sh
	-ln `pwd`/copydb.sh ../copydb.sh
	-ln `pwd`/updatedb.sh ../updatedb.sh

uninstall:
	-rm ../clean.sh
	-rm ../copydb.sh
	-rm ../updatedb.sh

clean:
	@echo "Nothing to do"
