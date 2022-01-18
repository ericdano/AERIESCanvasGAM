#Get-ADUser -Server plato -SearchBase "OU=Students,DC=student,DC=acalanes,DC=k12,DC=ca,DC=us" -Filter * -properties *| select Name, samAccountName, telephoneNumber, Pager 
Get-ADUser -Server plato -SearchBase "OU=Students,DC=student,DC=acalanes,DC=k12,DC=ca,DC=us" -Filter * -properties * |            
ForEach-Object {
  Set-ADUser -Server plato -Identity $_.samAccountName -Replace @{Pager=$_.samAccountName}
 }     
# And Verify it went well. 
#Get-ADUser -Server plato -SearchBase "OU=Students,DC=student,DC=acalanes,DC=k12,DC=ca,DC=us" -Filter * -properties *| select Name, samAccountName, telephoneNumber, Pager 