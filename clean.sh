#!/bin/sh
for i in `find . -type d -name appengine -o -name deploy`
do
	if [[ "$i" =~ ".git" ]]
	then
		continue
	elif [ ! -x $i/vi ]
	then
		continue
	fi

	echo -n "Clearing $i..."
	rm -rf $i/vi/*
	if [ $? -ne 0 ]
	then
		echo "Failed"
	else
		echo "Done"
	fi
done

find . -name "*.pyc" -exec rm -f {} \;

for i in `find . -name "_pyjs.js"`
do
	clear="`dirname $i`"
	echo -n "Clearing $clear..."

	rm -rf "$clear"
	echo "Ok!"
done

