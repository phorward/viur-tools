#!/bin/sh
TMPDIR=/tmp
DBDIR=$HOME/DB

cd $DBDIR
if [ $? -ne 0 ]
then
	echo "No DB directory in $HOME found."
	exit 1
fi

choice=0
dirlist=`ls -t *.tar.gz | sed -e 's/\.tar\.gz$//g'`

while true
do
	cnt=0
	sel=""

	echo "---"

	for i in $dirlist
	do
		if [ $cnt -eq $choice ]
		then
			printf "> %2d %s\n" $cnt $i
			sel=$i
		else
			printf "  %2d %s\n" $cnt $i
		fi

		cnt=`expr $cnt + 1`
	done

	if [ $cnt -eq 0 ]
	then
		echo "No Databases available."
		exit 1
	fi

	printf "Select [%s]>" $sel
	read nchoice

	if [ -z "$nchoice" ]
	then
		b=`basename $sel`

		targetdir="$TMPDIR/appengine.$b.`whoami`"

		if [ -d "$targetdir" ]
		then
			echo -n "$targetdir already exists, deleting..."

			rm -rf "$targetdir"
			if [ $? -ne 0 ]
			then
				echo "Error deleting directory"
				exit 1
			fi

			echo "Done"
		fi

		echo -n "Unpacking '$sel' into '$targetdir'..."

		mkdir $targetdir
		if [ $? -ne 0 ]
		then
			echo "Error creating directory"
			exit 1
		fi

		chmod 700 $targetdir

		#rsync -a --delete $sel/ /tmp/appengine.$b.`whoami`/
		tar xfz $sel.tar.gz --strip-components=1 -C $targetdir

		if [ $? -ne 0 ]
		then
			echo "Error unpacking"
			exit 1
		fi

		echo "Done"
		break
	fi

	if [ $nchoice -ge $cnt -o $nchoice -lt 0 ]
	then
		echo "Invalid selection!"
		continue
	fi

	choice=$nchoice
done

