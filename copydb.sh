#!/bin/sh

cd $HOME/DB
if [ $? -ne 0 ]
then
	echo "No DB directory in $HOME found."
	exit 1
fi

choice=0
dirlist=`ls -dt1 */ | sed -e 's/\/$//g'`

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

		echo -n "Copy '$sel' into 'appengine.$b.`whoami`'..."
		rsync -a --delete $sel/ /tmp/appengine.$b.`whoami`/
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

