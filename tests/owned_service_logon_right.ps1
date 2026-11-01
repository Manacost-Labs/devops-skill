# Only the guarded, disposable native fixture may load this owner-side helper.
if($env:GITHUB_ACTIONS -cne 'true' -or $env:RUNNER_ENVIRONMENT -cne 'github-hosted' -or $env:DEVOPS_OWNED_JEA_FIXTURE -cne '1'){throw 'Owned fixture context required'}
Add-Type -TypeDefinition @'
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Runtime.InteropServices;
using System.Security.Principal;
public static class DevopsOwnedServiceLogonRight {
  const string Right="SeServiceLogonRight";
  [StructLayout(LayoutKind.Sequential)] struct Attributes {
    public uint Length; public IntPtr Root,Name; public uint Flags; public IntPtr Descriptor,Qos;
  }
  [StructLayout(LayoutKind.Sequential)] struct Text {
    public ushort Length,Maximum; public IntPtr Buffer;
  }
  [DllImport("advapi32.dll")] static extern uint LsaOpenPolicy(IntPtr system,ref Attributes attributes,uint access,out IntPtr policy);
  [DllImport("advapi32.dll")] static extern uint LsaClose(IntPtr policy);
  [DllImport("advapi32.dll")] static extern uint LsaFreeMemory(IntPtr memory);
  [DllImport("advapi32.dll")] static extern uint LsaNtStatusToWinError(uint status);
  [DllImport("advapi32.dll")] static extern uint LsaEnumerateAccountRights(IntPtr policy,byte[] sid,out IntPtr rights,out uint count);
  [DllImport("advapi32.dll")] static extern uint LsaAddAccountRights(IntPtr policy,byte[] sid,Text[] rights,uint count);
  [DllImport("advapi32.dll")] static extern uint LsaRemoveAccountRights(IntPtr policy,byte[] sid,[MarshalAs(UnmanagedType.U1)] bool all,Text[] rights,uint count);
  static void Check(uint status) { if(status!=0) throw new Win32Exception((int)LsaNtStatusToWinError(status)); }
  static byte[] Sid(string value) {
    SecurityIdentifier sid=new SecurityIdentifier(value);
    if(!value.StartsWith("S-1-5-21-",StringComparison.Ordinal)) throw new ArgumentException("Owned local SID required");
    byte[] bytes=new byte[sid.BinaryLength];sid.GetBinaryForm(bytes,0);return bytes;
  }
  static IntPtr Open(uint access) {
    Attributes attributes=new Attributes();attributes.Length=(uint)Marshal.SizeOf(typeof(Attributes));
    IntPtr handle;Check(LsaOpenPolicy(IntPtr.Zero,ref attributes,access,out handle));return handle;
  }
  public static string[] Read(string value) {
    byte[] sid=Sid(value);IntPtr policy=Open(0x800),memory=IntPtr.Zero;
    try {
      uint count;uint status=LsaEnumerateAccountRights(policy,sid,out memory,out count);
      if(status!=0 && LsaNtStatusToWinError(status)==2) return new string[0];
      Check(status);if(count>128) throw new InvalidOperationException("Unbounded account rights");
      List<string> result=new List<string>();int size=Marshal.SizeOf(typeof(Text));
      for(int i=0;i<count;i++) {
        Text text=(Text)Marshal.PtrToStructure(IntPtr.Add(memory,i*size),typeof(Text));
        if(text.Length>256 || text.Length%2!=0 || text.Buffer==IntPtr.Zero) throw new InvalidOperationException("Invalid account right");
        result.Add(Marshal.PtrToStringUni(text.Buffer,text.Length/2));
      }
      return result.ToArray();
    } finally {if(memory!=IntPtr.Zero) LsaFreeMemory(memory);LsaClose(policy);}
  }
  public static void Set(string value,bool add) {
    byte[] sid=Sid(value);IntPtr policy=Open(add?0x810u:0x800u),buffer=Marshal.StringToHGlobalUni(Right);
    try {
      Text text=new Text();text.Length=(ushort)(Right.Length*2);text.Maximum=(ushort)(text.Length+2);text.Buffer=buffer;
      if(add) Check(LsaAddAccountRights(policy,sid,new Text[]{text},1));
      else if(Array.IndexOf(Read(value),Right)>=0) Check(LsaRemoveAccountRights(policy,sid,false,new Text[]{text},1));
    } finally {Marshal.FreeHGlobal(buffer);LsaClose(policy);}
  }
}
'@
