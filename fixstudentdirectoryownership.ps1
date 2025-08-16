# Fix Student H Drive Permissions
# Requires the Active Directory module for PowerShell
Import-Module ActiveDirectory

$Users = Import-Csv -Path $args[0]

# Loop through each user in the CSV file
foreach ($User in $Users) {

    # Create the SamAccountName (username) from the first part of the email address
    $SamAccountName = $User.STUID
    # Construct the home directory path
    $HomeDirectory = $User.HDrive
    # Set permissions for the new directory
    # This example grants full control to the user and removes inheritance
    $Acl = Get-Acl $HomeDirectory
    $Rule = New-Object System.Security.AccessControl.FileSystemAccessRule($SamAccountName, "FullControl", "ContainerInherit,ObjectInherit", "None", "Allow")
    $Acl.SetAccessRule($Rule)
    Set-Acl -Path $HomeDirectory -AclObject $Acl
    Write-Host "Home directory $($HomeDirectory) has been created and permissions set."
    
}

