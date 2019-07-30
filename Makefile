
nothing:
	@echo "Either type 'make install' or 'make uninstall' to set/unset symlinks"

install:
	ln -s `pwd`/clean.sh ../clean.sh
	ln -s `pwd`/copydb.sh ../copydb.sh
	ln -s `pwd`/updatedb.sh ../updatedb.sh

uninstall:
	test -h ../clean.sh && rm ../clean.sh
	test -h ../copydb.sh && rm ../copydb.sh
	test -h ../updatedb.sh && rm ../updatedb.sh

