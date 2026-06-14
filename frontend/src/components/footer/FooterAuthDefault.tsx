/*eslint-disable*/
export default function Footer() {
  return (
    <div className="z-[5] mx-auto flex w-full max-w-screen-sm flex-col items-center justify-center px-[20px] pb-4 lg:mb-6 lg:max-w-[100%] xl:mb-2 xl:w-[1310px] xl:pb-6">
      <p className="text-center text-sm text-gray-600 md:text-base">
        ©{new Date().getFullYear()} Invoce. 保留所有权利。
      </p>
    </div>
  );
}
