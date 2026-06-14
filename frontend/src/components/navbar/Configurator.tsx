// Chakra Imports
import {
  Drawer,
  DrawerBody,
  DrawerCloseButton,
  DrawerContent,
  DrawerHeader,
} from '@chakra-ui/modal';
import { useDisclosure } from '@chakra-ui/hooks';
import React from 'react';
import Light from '/public/img/layout/Light.png';
import Dark from '/public/img/layout/Dark.png';
import DefaultSidebar from '/public/img/layout/DefaultSidebar.png';
import DefaultSidebarDark from '/public/img/layout/DefaultSidebarDark.png';
import MiniSidebar from '/public/img/layout/MiniSidebar.png';
import MiniSidebarDark from '/public/img/layout/MiniSidebarDark.png';
import ConfiguratorLogo from '/public/img/layout/ConfiguratorLogo.png';
import Image from 'next/image';
// Assets
import { MdSettings } from 'react-icons/md';
import ConfiguratorRadio from './ConfiguratorRadio';

// 外观设置面板：仅保留两项真实功能——主题（浅色/深色）与侧边栏（展开/收起）。
// 用 darkmode prop 驱动选中态与预览图，避免在 render 中读取 document（SSR/水合反模式）。
export default function Configurator(props: {
  mini: boolean;
  setMini: (value: boolean) => void;
  darkmode: boolean;
  setDarkmode: (value: boolean) => void;
  theme?: any; // navbar 透传但本面板未使用
  setTheme?: any;
}) {
  const { mini, setMini, darkmode, setDarkmode } = props;
  const { isOpen, onOpen, onClose } = useDisclosure();
  const btnRef = React.useRef<HTMLButtonElement>(null);
  return (
    <>
      <button
        ref={btnRef}
        aria-label="外观设置"
        className="h-[18px] min-h-[unset] w-max min-w-[unset] bg-none p-0"
        onClick={onOpen}
      >
        <MdSettings className="h-[18px] w-[18px] text-gray-400 dark:text-white" />
      </button>
      <Drawer isOpen={isOpen} onClose={onClose} placement="right">
        <DrawerContent className="my-4 ml-0 mr-4 w-[calc(100vw_-_32px)] max-w-[calc(100vw_-_32px)] rounded-2xl bg-white shadow-[-20px_17px_40px_4px_rgba(112,_144,_176,_0.18)] dark:bg-navy-800 dark:shadow-[-22px_32px_51px_4px_#0B1437] sm:ml-4 md:w-[400px] md:max-w-[400px]">
          <DrawerHeader
            px="28px"
            w={{ base: '100%', md: '400px' }}
            pt="24px"
            pb="0px"
          >
            <DrawerCloseButton className="absolute right-[26px] top-[16px] h-4 w-4 text-gray-900 dark:text-white" />
            <div className="flex items-center">
              <div className="relative mr-5 flex h-12 w-12 rounded-full bg-gradient-to-b from-brand-400 to-brand-600">
                <Image
                  fill
                  style={{ objectFit: 'contain' }}
                  alt=""
                  src={ConfiguratorLogo}
                />
              </div>
              <div>
                <p className="text-xl font-bold text-gray-900 dark:text-white">
                  外观设置
                </p>
                <p className="text-md flex font-medium text-gray-600">
                  主题与侧边栏
                </p>
              </div>
            </div>
            <div className="my-[30px] h-px w-full bg-gray-200 dark:!bg-navy-700" />
          </DrawerHeader>
          <DrawerBody
            overflowY="scroll"
            px="28px"
            pt="0px"
            pb="24px"
            w={{ base: '100%', md: '400px' }}
            maxW="unset"
          >
            <div className="flex flex-col">
              <p className="mb-3 font-bold text-gray-900 dark:text-white">
                主题模式
              </p>
              <div className="mb-7 flex w-full justify-between gap-5">
                <ConfiguratorRadio
                  onClick={() => {
                    if (darkmode) {
                      document.body.classList.remove('dark');
                      setDarkmode(false);
                    }
                  }}
                  active={!darkmode}
                  label={
                    <p className="font-bold text-gray-900 dark:text-white">
                      浅色
                    </p>
                  }
                >
                  <div className="relative h-[70px] w-full">
                    <Image
                      fill
                      style={{ objectFit: 'contain' }}
                      className="max-w-[130px] rounded-lg"
                      src={Light}
                      alt="浅色主题预览"
                    />
                  </div>
                </ConfiguratorRadio>
                <ConfiguratorRadio
                  onClick={() => {
                    if (!darkmode) {
                      document.body.classList.add('dark');
                      setDarkmode(true);
                    }
                  }}
                  active={darkmode}
                  label={
                    <p className="font-bold text-gray-900 dark:text-white">
                      深色
                    </p>
                  }
                >
                  <div className="relative h-[70px] w-full">
                    <Image
                      fill
                      style={{ objectFit: 'contain' }}
                      className="max-w-[130px] rounded-lg"
                      alt="深色主题预览"
                      src={Dark}
                    />
                  </div>
                </ConfiguratorRadio>
              </div>
              <p className="mb-3 font-bold text-gray-900 dark:text-white">
                侧边栏
              </p>
              <div className="mb-7 flex w-full justify-between gap-5">
                <ConfiguratorRadio
                  onClick={() => setMini(false)}
                  active={!mini}
                  label={
                    <p className="font-bold text-gray-900 dark:text-white">
                      展开
                    </p>
                  }
                >
                  <div className="relative flex min-h-[126px] w-[130px] items-center justify-center overflow-hidden rounded-[10px] border-[1px] border-gray-200 bg-gray-100 bg-repeat pl-2.5 pt-2.5 dark:border-[#323B5D] dark:bg-navy-900">
                    <Image
                      fill
                      style={{ objectFit: 'contain' }}
                      className="mx-auto my-auto max-h-[70px] max-w-full rounded-md shadow-[0px_6px_14px_rgba(200,_207,_215,_0.6)] dark:shadow-none md:max-w-[96px]"
                      alt="展开侧边栏预览"
                      src={darkmode ? DefaultSidebarDark : DefaultSidebar}
                    />
                  </div>
                </ConfiguratorRadio>
                <ConfiguratorRadio
                  onClick={() => setMini(true)}
                  active={mini}
                  label={
                    <p className="font-bold text-gray-900 dark:text-white">
                      收起
                    </p>
                  }
                >
                  <div className="relative flex min-h-[126px] w-[130px] items-center justify-center overflow-hidden rounded-[10px] border-[1px] border-gray-200 bg-gray-100 bg-repeat pl-2.5 pt-2.5 dark:border-[#323B5D] dark:bg-navy-900">
                    <Image
                      fill
                      style={{ objectFit: 'contain' }}
                      className="mx-auto my-auto max-h-[70px] max-w-full rounded-md shadow-[0px_6px_14px_rgba(200,_207,_215,_0.6)] dark:shadow-none md:max-w-[75px]"
                      alt="收起侧边栏预览"
                      src={darkmode ? MiniSidebarDark : MiniSidebar}
                    />
                  </div>
                </ConfiguratorRadio>
              </div>
            </div>
          </DrawerBody>
        </DrawerContent>
      </Drawer>
    </>
  );
}
