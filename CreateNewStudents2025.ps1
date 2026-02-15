# Student AD Creation Script 2025
# Usage
# H:\CreateStudentAccounts2025.ps1 thisfile.csv
# Requires the Active Directory module for PowerShell
# This might need to be run twice as domain controllers are a little laggy and do not set the home directory permissions
# as they haven't synced the newly created accounts from the primary domain server


Import-Module ActiveDirectory

$Users = Import-Csv -Path $args[0]
# Loop through each user in the CSV file
foreach ($User in $Users) {

    # Create the SamAccountName (username) from the first part of the email address
    $SamAccountName = $User.STUID
    $DisplayName = "$($User.LN), $($User.FN)"
    # Create the user's UPN (User Principal Name)
    $UserPrincipalName = $User.EMAIL
    # $OU = "OU=$($User.OU2),OU=$($User.OU1),OU=Students,DC=student,DC=acalanes,DC=k12,DC=ca,DC=us"
    $OU = "OU=$($User.OU1),OU=Students,DC=student,DC=acalanes,DC=k12,DC=ca,DC=us"
    # User Password
    $StudentPassword = $User.Password
    $ADDescription = $User.Description
    # Construct the home directory path
    $HomeDirectory = $User.HDrive
    # Create the user account in Active Directory
    New-ADUser -Server socrates -Name $User.DISPLAYNAME -GivenName $User.FN -Surname $User.LN -SamAccountName $User.STUID -DisplayName $DisplayName -UserPrincipalName $User.STUID -Path $OU -AccountPassword (ConvertTo-SecureString $User.PASSWORD -AsPlainText -Force) -Enabled $true -EmailAddress $User.EMAIL -ChangePasswordAtLogon $false -PasswordNeverExpires $true -CannotChangePassword $true -HomeDrive "H:" -HomeDirectory $User.HDrive -Description $ADDescription

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
}

