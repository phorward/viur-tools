#!/bin/sh

cd /tmp
if [ $? -ne 0 ]
then
	echo "No /tmp directory??"
	exit 1
fi

if [ ! -d $HOME/DB ]
then
	echo "No DB directory in $HOME found."
	exit 1
fi

choice=0
dirlist=`ls -dt1 appengine.*.*/`

while true
do
	cnt=0
	sel=""
	selname=""

	echo "---"

	for i in $dirlist
	do
		name=`echo $i | cut -f 2 -d '.'`
		if [ $cnt -eq $choice ]
		then
			printf "> %2d %s\n" $cnt $name
			sel=$i
			selname=$name
		else
			printf "  %2d %s\n" $cnt $name
		fi

		cnt=`expr $cnt + 1`
	done

	if [ $cnt -eq 0 ]
	then
		echo "No Databases available."
		exit 1
	fi

	printf "Select [%s]>" $selname
	read nchoice

	if [ -z "$nchoice" ]
	then
		echo -n "Copy '$sel' into $HOME/DB/$selname/..."
		rsync -a --delete $sel $HOME/DB/$selname/
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

