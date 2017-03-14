# -*- mode: python -*-

block_cipher = None


a = Analysis(['F:\\Workspace\\eclipse\\_python\\licreator\\lic_3.1.222_src\\src\\Lic.py'],
             pathex=['F:\\Workspace\\eclipse\\_python\\licreator\\lic_3.1.222_pyinst'],
             binaries=[],
             datas=[],
             hiddenimports=[],
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher)
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          name='licreator',
          debug=False,
          strip=False,
          upx=True,
          console=False , icon='F:\\Workspace\\eclipse\\_python\\licreator\\lic_3.1.222_src\\images\\lic_logo.ico')
