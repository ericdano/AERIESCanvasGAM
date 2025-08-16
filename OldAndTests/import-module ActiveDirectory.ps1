import-module ActiveDirectory
Import-csv "h:\passwordreset2022.csv" | ForEach-Object {
$samAccountName = $_."ID"
$newpassword = $_."New"
 set-adaccountpassword -Server socrates -Identity $samAccountName -NewPassword(ConvertTo-SecureString -asplaintext $newpassword -Force)
}