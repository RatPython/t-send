#!/usr/local/bin/perl
use File::Path;
use DBI;
use DBD::SQLite;
use File::stat;
use Time::localtime;

$porog='200000000000';

$current_time = time();

$dir='/volume3/down';
$busy="$dir/chkspace.flag";
$db="$dir/scripts/queue.db";

$host='127.0.0.1';
$port='58846';
$user="mt";
$passwd="master24";

$auth='127.0.0.1 --auth mt:master24';


if (-e $busy) { 
    $file_tstamp = stat($busy)->mtime;
    $age = $current_time - $file_tstamp;
    if ($age>3600)
     { system("rm '$busy'"); }
     else { exit; } ;
     }
 
open(F,">$busy");
print F "1";
close(F);





#$auth='127.0.0.1:5577 --auth mt:Master24!';



#$porog='0';


#my $host = "localhost"; # MySQL-сервер нашего хостинга
#my $port = "3306"; # порт, на который открываем соединение
#my $user = "root"; # имя пользователя
#my $pass = "ukffkm"; # пароль
#my $db = "down"; # имя базы данных

#$connection = DBI->connect("DBI:mysql:$db:$host:$port", $user,$pass);

#$connection = DBI->connect("DBI:mysql:$db:$host:$port", $user,$pass);

$rc=0;

$sp=getPr($dir);
print "[$sp]\n[$porog]\n";


if ($sp>$porog)
    {

    $connection = DBI->connect("dbi:SQLite:dbname=$db","","",{RaiseError => 1, AutoCommit => 1});
    $q="select * from queue where copied=1 and deleted=0 order by id";
    $statement = $connection->prepare($q);
    $statement->execute();


    while ($sp>$porog)
    {
     print "$sp > $porog\n";
     
     @row = $statement->fetchrow_array();
     $id=$row[0];
     $tid=$row[1];
     $fn=$row[3];
     $hash=$row[2];

     if ($id eq '') { last; }
    
#    ($id,$hash,$fn)=split('\|',$ln,3);
    print "    [$fn]    ($id,$tid,$hash)\n";
    
    $cmd="/volume1/\@appstore/transmission/bin/transmission-remote $auth -t $hash --remove-and-delete";
    # $cmd="$deluge \"connect $host:$port $user $passwd ; del --remove_data $tid ; exit\"";

    print "$cmd\n";
    system($cmd);
    
    sleep(10);
    
    
    $q1="delete from queue where id=$id";
    $st = $connection->prepare($q1);
    $st->execute();

    $sp=getPr($dir);
    $rc=1;
    }
    print "Usage: [$sp] <= [$porog]\n";

}


system("rm $busy");




exit($rc);


sub getPr()
{
 $sh=shift;
    my $c=`du -sb '$sh'`;
    chomp($c);
    #print "[$c]\n";;
    $c=~s/[ ]+/ /gi;
    my @sp=split(' ',$c);
    my $pr=$sp[0];
    $pr=~s/\%//;
#    print "sp:[$pr]";;
    return $pr;
}


