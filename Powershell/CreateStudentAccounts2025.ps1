# Requires the Active Directory module for PowerShell
Import-Module ActiveDirectory

# Define the OU where the new users will be created


# might need actual domain server to be addressed, ie PARIS or whatever
# Define the path for the home directories
# HomePath = "\\ahsacad-nas\students\"
# Above is for AHS students
# Read user data from a CSV file (e.g., users.csv)
# The CSV should have columns like 'FirstName', 'LastName', 'Email', etc.
# Description is  AHS GR 10 Student
# Only E-Mail has info in it
# \\ahsacad-nas\2029Gr4ade\StudentNumber
# Student number goes into Pager Field
# KIX_AHSACAD

# CHANGE THESE BEFORE RUNNING!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
$OU = "OU=Freshman,OU=MHS,OU=Students,DC=student,DC=acalanes,DC=k12,DC=ca,DC=us"
$Users = Import-Csv -Path "H:\MHS_FRESHMAN_2025.csv"
$Group = "MHS Grade 9 Students"
$Group2 = "KIX_MHSACAD"
$ADDescription = "MHS Grade 9 Student"

# Loop through each user in the CSV file
foreach ($User in $Users) {

    # Create the SamAccountName (username) from the first part of the email address
    $SamAccountName = $User.STUID
    $DisplayName = "$($User.LN), $($User.FN)"
    # Create the user's UPN (User Principal Name)
    $UserPrincipalName = $User.EMAIL

    # User Password
    $StudentPassword = $User.Password

    # Construct the home directory path
    $HomeDirectory = $User.HDrive
    # Create the user account in Active Directory
    New-ADUser -Server socrates -Name $User.DISPLAYNAME -GivenName $User.FN -Surname $User.LN -SamAccountName $User.STUID -DisplayName $DisplayName -UserPrincipalName $User.STUID -Path $OU -AccountPassword (ConvertTo-SecureString $User.PASSWORD -AsPlainText -Force) -Enabled $true -EmailAddress $User.EMAIL -ChangePasswordAtLogon $false -PasswordNeverExpires $true -CannotChangePassword $true -HomeDrive "H:" -HomeDirectory $User.HDrive -Description $ADDescription

    # Add the newly created user to the Students and the KIX
    Add-ADGroupMember -server socrates -Identity $Group -Members $SamAccountName
    Add-ADGroupMember -server socrates -Identity $Group2 -Members $SamAccountName
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

