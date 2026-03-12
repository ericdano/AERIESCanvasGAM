$Users = Import-Csv -Path "H:\CreateSubs.csv"            
foreach ($User in $Users)            
{            
    $Displayname = $User.firstname + " " + $User.lastname            
    $UserFirstname = $User.firstname            
    $UserLastname = $User.lastname            
    $ADOU = "OU=Subs,OU=Acad Staff,DC=staff,DC=acalanes,DC=k12,DC=ca,DC=us"           
    $SAM = $User.SAM            
    $UPN = $User.SAM + "@acalanes.k12.ca.us"          
    $Description = $UserLastname + " " + $UserFirstname          
    $Password = "password"     
    $email = $User.email     
    New-ADUser -Name $Displayname -EmailAddress $email -DisplayName $Displayname -SamAccountName $SAM -UserPrincipalName $UPN -GivenName $UserFirstname -Surname $UserLastname -Description $UserLastname -Office $UserLastname -AccountPassword (ConvertTo-SecureString $Password -AsPlainText -Force) -Enabled $true -Path $ADOU -ChangePasswordAtLogon $false -PasswordNeverExpires $true -server paris
}
