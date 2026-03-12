# Account Creation for Hourly/Volunteers in AD2025
# Requires the Active Directory module for PowerShell
# This script is called from Python to create AD accounts

Import-Module ActiveDirectory

$User = $args[0]
$accountname $arg[1]
$campus = $arg[2]
$temppassword = $arg[3]

# Loop through each user in the CSV file

# Create the SamAccountName (username) from the first part of the email address
$SamAccountName = $User.STUID
$DisplayName = "$($User.LN), $($User.FN)"
# Create the user's UPN (User Principal Name)
$UserPrincipalName = $User.EMAIL
$OU = "OU=$($User.OU2),OU=$($User.OU1),OU=Staff,OU=$,DC=staff,DC=acalanes,DC=k12,DC=ca,DC=us"
# User Password
$StudentPassword = $User.Password
$ADDescription = $User.Description
# Create the user account in Active Directory
New-ADUser -Server socrates -Name $User.DISPLAYNAME -GivenName $User.FN -Surname $User.LN -SamAccountName $accountname -DisplayName $DisplayName -UserPrincipalName $User.STUID -Path $OU -AccountPassword (ConvertTo-SecureString $User.PASSWORD -AsPlainText -Force) -Enabled $true -EmailAddress $User.EMAIL -ChangePasswordAtLogon $false -PasswordNeverExpires $true -CannotChangePassword $true -HomeDrive "H:" -HomeDirectory $User.HDrive -Description $ADDescription

# Add the newly created user to the Students and the KIX
Add-ADGroupMember -server socrates -Identity $User.Group1 -Members $SamAccountName
Add-ADGroupMember -server socrates -Identity $User.Group2 -Members $SamAccountName
# Output a message to confirm the user was created
Write-Host "User $($SamAccountName) $($DisplayName) has been created in Active Directory."

    # Create the home directory and set permissions
    if (!(Test-Path -Path $HomeDirectory)) {
        New-Item -Path $HomeDirectory -ItemType Directory
        # Set permissions for the new directory
        # This example grants full control to the user and removes inheritance
        $Acl = Get-Acl $HomeDirectory
        $Rule = New-Object System.Security.AccessControl.FileSystemAccessRule($SamAccountName, "FullControl", "ContainerInherit,ObjectInherit", "None", "Allow")
        $Acl.SetAccessRule($Rule)
        Set-Acl -Path $HomeDirectory -AclObject $Acl
        Write-Host "Home directory $($HomeDirectory) has been created and permissions set."
    }